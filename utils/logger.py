import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance."""
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist to avoid duplicate logs
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        logger.addHandler(ch)
        
    return logger
