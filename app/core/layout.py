"""Shared HTML layout utilities for consistent page structure."""
from typing import Optional


def get_sidebar_html(current_page: Optional[str] = None) -> str:
    """Generate sidebar navigation HTML.
    
    Args:
        current_page: Current page identifier ('files', 'templates', 'upload', 'upload_template', or None)
        
    Returns:
        HTML string for sidebar
    """
    files_active = 'active' if current_page == 'files' else ''
    templates_active = 'active' if current_page == 'templates' else ''
    upload_active = 'active' if current_page == 'upload' else ''
    upload_template_active = 'active' if current_page == 'upload_template' else ''
    
    return f"""
    <div class="sidebar">
        <div class="sidebar-header">
            <h2>MGA Bordereaux</h2>
        </div>
        <nav class="sidebar-nav">
            <a href="/files" class="nav-item {files_active}">
                <span class="nav-icon">📄</span>
                <span class="nav-text">Files</span>
            </a>
            <a href="/mappings" class="nav-item {templates_active}">
                <span class="nav-icon">📋</span>
                <span class="nav-text">Templates</span>
            </a>
            <button onclick="openModal('upload-file-modal')" class="nav-item {upload_active}">
                <span class="nav-icon">⬆️</span>
                <span class="nav-text">Upload File</span>
            </button>
            <button onclick="openModal('upload-template-modal')" class="nav-item {upload_template_active}">
                <span class="nav-icon">📤</span>
                <span class="nav-text">Upload Template</span>
            </button>
        </nav>
    </div>
    """


def get_layout_css() -> str:
    """Get shared CSS for layout with sidebar."""
    return """
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    body {
        font-family: 'Helvetica Neue', Arial, 'Segoe UI', Roboto, sans-serif;
        background: #f8f9fa;
        color: #1a1a1a;
        display: flex;
        min-height: 100vh;
    }
    .sidebar {
        width: 250px;
        background: white;
        border-right: 1px solid #e9ecef;
        display: flex;
        flex-direction: column;
        position: fixed;
        height: 100vh;
        overflow-y: auto;
    }
    .sidebar-header {
        padding: 24px 20px;
        border-bottom: 1px solid #e9ecef;
    }
    .sidebar-header h2 {
        color: #003781;
        font-size: 20px;
        font-weight: 600;
        letter-spacing: -0.5px;
    }
    .sidebar-nav {
        padding: 16px 0;
    }
    .nav-item {
        display: flex;
        align-items: center;
        padding: 12px 20px;
        color: #495057;
        text-decoration: none;
        transition: all 0.2s;
        border-left: 3px solid transparent;
        cursor: pointer;
        border: none;
        background: none;
        width: 100%;
        text-align: left;
    }
    .nav-item:hover {
        background: #f8f9fa;
        color: #003781;
    }
    .nav-item.active {
        background: #f0f4ff;
        color: #003781;
        border-left-color: #003781;
        font-weight: 500;
    }
    .nav-icon {
        font-size: 18px;
        margin-right: 12px;
        width: 24px;
        text-align: center;
    }
    .nav-text {
        font-size: 14px;
    }
    .main-content {
        flex: 1;
        margin-left: 250px;
        padding: 24px 30px 30px 30px;
        min-height: 100vh;
    }
    .content-container {
        max-width: 1400px;
        margin: 0 auto;
        background: white;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        padding: 0 40px 40px 40px;
    }
    .content-container h1:first-child {
        margin-top: 0;
        padding-top: 0;
    }
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        align-items: center;
        justify-content: center;
    }
    .modal-overlay.show {
        display: flex;
    }
    .modal {
        background: white;
        border-radius: 4px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        max-width: 600px;
        width: 90%;
        max-height: 90vh;
        overflow-y: auto;
        position: relative;
    }
    .modal-header {
        padding: 20px 24px;
        border-bottom: 1px solid #e9ecef;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .modal-header h2 {
        color: #003781;
        font-size: 20px;
        font-weight: 600;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .modal-close {
        background: none;
        border: none;
        font-size: 24px;
        color: #6c757d;
        cursor: pointer;
        padding: 0;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        transition: all 0.2s;
    }
    .modal-close:hover {
        background: #f8f9fa;
        color: #003781;
    }
    .modal-body {
        padding: 24px;
    }
    @media (max-width: 768px) {
        .sidebar {
            width: 200px;
        }
        .main-content {
            margin-left: 200px;
            padding: 20px;
        }
        .modal {
            width: 95%;
            max-height: 95vh;
        }
    }
    """


def wrap_with_layout(content: str, page_title: str, current_page: Optional[str] = None, additional_css: str = "", additional_scripts: str = "") -> str:
    """Wrap page content with shared layout including sidebar.
    
    Args:
        content: Main content HTML
        page_title: Page title for <title> tag
        current_page: Current page identifier for active nav state
        additional_css: Additional CSS to include in the page
        additional_scripts: Additional JavaScript to include at the end of the body
        
    Returns:
        Complete HTML page with layout
    """
    sidebar = get_sidebar_html(current_page)
    layout_css = get_layout_css()
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title}</title>
        <style>
            {layout_css}
            {additional_css}
        </style>
    </head>
    <body>
        {sidebar}
        <div class="main-content">
            <div class="content-container">
                {content}
            </div>
        </div>
        
        <!-- Modal Overlay -->
        <div class="modal-overlay" id="modal-overlay" onclick="closeModalOnOverlay(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <div id="modal-content"></div>
            </div>
        </div>
        
        <script>
            function openModal(modalId) {{
                let url = '';
                if (modalId === 'upload-file-modal') {{
                    url = '/files/upload/modal';
                }} else if (modalId === 'upload-template-modal') {{
                    url = '/mappings/upload/modal';
                }}
                
                if (url) {{
                    fetch(url)
                        .then(response => response.text())
                        .then(html => {{
                            const modalContent = document.getElementById('modal-content');
                            modalContent.innerHTML = html;
                            
                            // Execute any scripts in the loaded HTML
                            const scripts = modalContent.querySelectorAll('script');
                            scripts.forEach(oldScript => {{
                                const newScript = document.createElement('script');
                                Array.from(oldScript.attributes).forEach(attr => {{
                                    newScript.setAttribute(attr.name, attr.value);
                                }});
                                newScript.appendChild(document.createTextNode(oldScript.innerHTML));
                                oldScript.parentNode.replaceChild(newScript, oldScript);
                            }});
                            
                            document.getElementById('modal-overlay').classList.add('show');
                            document.body.style.overflow = 'hidden';
                        }})
                        .catch(error => {{
                            console.error('Error loading modal:', error);
                        }});
                }}
            }}
            
            function closeModal() {{
                document.getElementById('modal-overlay').classList.remove('show');
                document.body.style.overflow = '';
                document.getElementById('modal-content').innerHTML = '';
            }}
            
            function closeModalOnOverlay(event) {{
                if (event.target.id === 'modal-overlay') {{
                    closeModal();
                }}
            }}
            
            // Close modal on Escape key
            document.addEventListener('keydown', function(event) {{
                if (event.key === 'Escape') {{
                    closeModal();
                }}
            }});
        </script>
        {additional_scripts}
    </body>
    </html>
    """

