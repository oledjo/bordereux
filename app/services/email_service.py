import email
from email.header import decode_header
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import imapclient
from imapclient import IMAPClient

from app.config import get_settings


class EmailService:
    """Service for reading emails from IMAP server."""
    
    def __init__(self):
        self.settings = get_settings()
        self._validate_imap_config()
    
    def _validate_imap_config(self) -> None:
        """Validate that IMAP configuration is complete."""
        if not self.settings.imap_host:
            raise ValueError("IMAP_HOST is required")
        if not self.settings.imap_username:
            raise ValueError("IMAP_USERNAME is required")
        if not self.settings.imap_password and not self.settings.imap_oauth_token:
            raise ValueError("Either IMAP_PASSWORD or IMAP_OAUTH_TOKEN is required")
    
    def _connect(self) -> IMAPClient:
        """Connect to IMAP server.
        
        Returns:
            Connected IMAPClient instance
            
        Raises:
            Exception: If connection fails
        """
        try:
            client = IMAPClient(
                self.settings.imap_host,
                port=self.settings.imap_port,
                ssl=True,
            )
            
            # Authenticate
            if self.settings.imap_oauth_token:
                # OAuth authentication (if supported by server)
                client.oauth2_login(
                    self.settings.imap_username,
                    self.settings.imap_oauth_token
                )
            else:
                # Password authentication
                client.login(
                    self.settings.imap_username,
                    self.settings.imap_password
                )
            
            return client
        except Exception as e:
            raise ConnectionError(f"Failed to connect to IMAP server: {str(e)}")
    
    def _decode_header(self, header_value: Optional[bytes]) -> str:
        """Decode email header value.
        
        Args:
            header_value: Header value as bytes or string
            
        Returns:
            Decoded string
        """
        if header_value is None:
            return ""
        
        if isinstance(header_value, str):
            return header_value
        
        decoded_parts = decode_header(header_value)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _parse_email_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse email date string to datetime.
        
        Args:
            date_str: Date string from email
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        if not date_str:
            return None
        
        try:
            # Parse email date format
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
    
    def _is_allowed_file_type(self, filename: str) -> bool:
        """Check if file type is allowed.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if file type is allowed
        """
        if not filename:
            return False
        
        # Get file extension (without dot)
        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        return extension in self.settings.allowed_file_types
    
    def _extract_attachments(self, msg: email.message.Message) -> List[Tuple[bytes, str]]:
        """Extract attachments from email message.
        
        Args:
            msg: Email message object
            
        Returns:
            List of tuples (attachment_bytes, filename)
        """
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                # Skip multipart containers
                if part.get_content_maintype() == 'multipart':
                    continue
                
                # Get attachment filename
                filename = part.get_filename()
                if filename:
                    filename = self._decode_header(filename)
                    
                    # Filter by allowed file types
                    if self._is_allowed_file_type(filename):
                        # Get attachment content
                        payload = part.get_payload(decode=True)
                        if payload:
                            attachments.append((payload, filename))
        
        return attachments
    
    def fetch_unread_emails(
        self,
        folder: str = "INBOX",
        mark_as_read: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch unread emails from specified folder.
        
        Args:
            folder: IMAP folder name (default: "INBOX")
            mark_as_read: Whether to mark emails as read after fetching
            
        Returns:
            List of dictionaries containing:
                - raw_bytes: Attachment file content as bytes
                - filename: Attachment filename
                - metadata: Dictionary with email metadata (sender, subject, date)
        """
        client = None
        results = []
        
        try:
            # Connect to IMAP server
            client = self._connect()
            
            # Select folder
            client.select_folder(folder)
            
            # Search for unread emails
            messages = client.search(['UNSEEN'])
            
            if not messages:
                return results
            
            # Fetch email data
            response = client.fetch(messages, ['RFC822', 'ENVELOPE'])
            
            for msg_id, data in response.items():
                try:
                    # Parse email message
                    raw_email = data[b'RFC822']
                    msg = email.message_from_bytes(raw_email)
                    
                    # Extract email metadata
                    sender = self._decode_header(msg.get('From', ''))
                    subject = self._decode_header(msg.get('Subject', ''))
                    date_str = msg.get('Date', '')
                    email_date = self._parse_email_date(date_str)
                    
                    # Extract attachments
                    attachments = self._extract_attachments(msg)
                    
                    # Create metadata dict
                    metadata = {
                        'sender': sender,
                        'subject': subject,
                        'date': email_date.isoformat() if email_date else None,
                        'email_id': msg_id,
                    }
                    
                    # Add each attachment to results
                    # Only add emails that have allowed attachments
                    for attachment_bytes, filename in attachments:
                        results.append({
                            'raw_bytes': attachment_bytes,
                            'filename': filename,
                            'metadata': metadata,
                        })
                    
                    # If no attachments found, skip this email (don't add to results)
                    
                    # Mark as read if requested
                    if mark_as_read:
                        client.set_flags([msg_id], [imapclient.SEEN])
                
                except Exception as e:
                    # Log error but continue processing other emails
                    print(f"Error processing email {msg_id}: {str(e)}")
                    continue
        
        except Exception as e:
            raise RuntimeError(f"Error fetching emails: {str(e)}")
        
        finally:
            # Close connection
            if client:
                try:
                    client.logout()
                except Exception:
                    pass
        
        return results
    
    def fetch_unread_emails_as_tuples(
        self,
        folder: str = "INBOX",
        mark_as_read: bool = False
    ) -> List[Tuple[bytes, str, Dict[str, Any]]]:
        """Fetch unread emails and return as list of tuples.
        
        Convenience method that returns data in tuple format:
        (raw_bytes, filename, metadata)
        
        Args:
            folder: IMAP folder name (default: "INBOX")
            mark_as_read: Whether to mark emails as read after fetching
            
        Returns:
            List of tuples: (raw_bytes, filename, metadata)
        """
        results = self.fetch_unread_emails(folder, mark_as_read)
        return [
            (item['raw_bytes'], item['filename'], item['metadata'])
            for item in results
        ]
    
    def mark_emails_as_seen(self, email_ids: List[int], folder: str = "INBOX") -> None:
        """Mark emails as seen.
        
        Args:
            email_ids: List of email message IDs to mark as seen
            folder: IMAP folder name (default: "INBOX")
        """
        if not email_ids:
            return
        
        client = None
        try:
            client = self._connect()
            client.select_folder(folder)
            client.set_flags(email_ids, [imapclient.SEEN])
        except Exception as e:
            raise RuntimeError(f"Error marking emails as seen: {str(e)}")
        finally:
            if client:
                try:
                    client.logout()
                except Exception:
                    pass
    
    def test_connection(self) -> bool:
        """Test IMAP connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            client = self._connect()
            client.logout()
            return True
        except Exception:
            return False

