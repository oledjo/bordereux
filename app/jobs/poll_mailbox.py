from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.email_service import EmailService
from app.services.storage_service import StorageService
from app.models.bordereaux import BordereauxFile, FileStatus
from app.core.logging import get_structured_logger


class PollMailboxJob:
    """Job to poll mailbox and store email attachments."""
    
    def __init__(self):
        self.email_service = EmailService()
        self.storage_service = StorageService()
        self.logger = get_structured_logger(__name__)
    
    def _update_file_status(self, db: Session, file_id: int, status: FileStatus) -> None:
        """Update bordereaux file status.
        
        Args:
            db: Database session
            file_id: File ID to update
            status: New status
        """
        bordereaux_file = db.query(BordereauxFile).filter(
            BordereauxFile.id == file_id
        ).first()
        
        if bordereaux_file:
            bordereaux_file.status = status
            db.commit()
    
    def run(self, folder: str = "INBOX") -> Dict[str, Any]:
        """Run the mailbox polling job.
        
        Fetches unread emails, saves attachments, updates file status to RECEIVED,
        and marks emails as seen if all attachments were processed successfully.
        
        Args:
            folder: IMAP folder to poll (default: "INBOX")
            
        Returns:
            Dictionary with job execution results:
                - processed_count: Number of attachments processed
                - duplicate_count: Number of duplicate files found
                - failed_count: Number of failed attachments
                - emails_marked_seen: Number of emails marked as seen
        """
        db = next(get_db())
        
        results = {
            "processed_count": 0,
            "duplicate_count": 0,
            "failed_count": 0,
            "emails_marked_seen": 0,
        }
        
        # Track attachments by email_id
        email_attachments: Dict[int, List[Dict]] = defaultdict(list)
        email_results: Dict[int, Dict[str, bool]] = defaultdict(lambda: {"success": True, "count": 0})
        
        try:
            # Log email poll start
            self.logger.info("Email poll started", folder=folder)
            
            # Fetch unread emails (don't mark as read yet)
            emails = self.email_service.fetch_unread_emails(
                folder=folder,
                mark_as_read=False
            )
            
            if not emails:
                self.logger.info("Email poll completed", folder=folder, emails_found=0)
                return results
            
            self.logger.info("Emails fetched", folder=folder, email_count=len(emails))
            
            # Group attachments by email_id
            for email_data in emails:
                email_id = email_data['metadata']['email_id']
                email_attachments[email_id].append(email_data)
            
            # Process each attachment
            for email_id, attachments in email_attachments.items():
                email_results[email_id]["count"] = len(attachments)
                
                for attachment in attachments:
                    try:
                        # Extract attachment data
                        raw_bytes = attachment['raw_bytes']
                        filename = attachment['filename']
                        metadata = attachment['metadata']
                        
                        sender = metadata['sender']
                        subject = metadata['subject']
                        date_str = metadata['date']
                        
                        # Parse date
                        received_at = None
                        if date_str:
                            try:
                                received_at = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            except Exception:
                                received_at = datetime.utcnow()
                        else:
                            received_at = datetime.utcnow()
                        
                        # Save file using storage service
                        save_result = self.storage_service.save_raw_file(
                            db=db,
                            file_bytes=raw_bytes,
                            filename=filename,
                            source_email=sender,
                            received_at=received_at,
                            subject=subject,
                        )
                        
                        file_id = save_result['file_id']
                        is_duplicate = save_result['is_duplicate']
                        
                        # Update status to RECEIVED
                        self._update_file_status(db, file_id, FileStatus.RECEIVED)
                        
                        if is_duplicate:
                            results["duplicate_count"] += 1
                            self.logger.info(
                                "File stored (duplicate)",
                                file_id=file_id,
                                filename=filename,
                                sender=sender,
                                email_id=email_id
                            )
                        else:
                            results["processed_count"] += 1
                            self.logger.info(
                                "File stored",
                                file_id=file_id,
                                filename=filename,
                                sender=sender,
                                email_id=email_id,
                                file_size=len(raw_bytes)
                            )
                        
                    except Exception as e:
                        self.logger.error(
                            "Error processing attachment",
                            filename=filename,
                            email_id=email_id,
                            error=str(e)
                        )
                        results["failed_count"] += 1
                        email_results[email_id]["success"] = False
            
            # Mark emails as seen if all attachments were processed successfully
            emails_to_mark_seen = [
                email_id
                for email_id, email_result in email_results.items()
                if email_result["success"]
            ]
            
            if emails_to_mark_seen:
                try:
                    self.email_service.mark_emails_as_seen(emails_to_mark_seen, folder)
                    results["emails_marked_seen"] = len(emails_to_mark_seen)
                    self.logger.info(
                        "Emails marked as seen",
                        folder=folder,
                        email_count=len(emails_to_mark_seen)
                    )
                except Exception as e:
                    self.logger.error(
                        "Error marking emails as seen",
                        folder=folder,
                        error=str(e)
                    )
            
            # Log email poll completion
            self.logger.info(
                "Email poll completed",
                folder=folder,
                processed_count=results["processed_count"],
                duplicate_count=results["duplicate_count"],
                failed_count=results["failed_count"],
                emails_marked_seen=results["emails_marked_seen"]
            )
        
        except Exception as e:
            self.logger.exception("Error in poll mailbox job", folder=folder, error=str(e))
            raise
        
        finally:
            # Close database session
            db.close()
        
        return results


def run_poll_mailbox_job(folder: str = "INBOX") -> Dict[str, Any]:
    """Convenience function to run the poll mailbox job.
    
    Args:
        folder: IMAP folder to poll (default: "INBOX")
        
    Returns:
        Dictionary with job execution results
    """
    job = PollMailboxJob()
    return job.run(folder=folder)

