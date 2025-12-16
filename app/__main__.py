"""
S11 Partner Local Knowledge Service Entry Point

This is the main entry point for the S11 service.
It starts:
1. Flask HTTP server for H28 API
2. RabbitMQ consumers for A32 (file import responses) and A33 (snapshot requests)
"""

import os
import sys
import threading
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def start_rabbitmq_consumers():
    """
    Start RabbitMQ consumers in separate threads:
    1. A32 Response Consumer: Handle file import responses from S15
    2. A33 Request Consumer: Handle snapshot requests from S12
    """
    from .services.MessageQueueService import MessageQueueService
    from .services import file_import_service, snapshot_service
    
    mq_lock = threading.Lock()
    
    # Get queue names from environment
    file_import_response_queue = os.getenv("FILE_IMPORT_RESPONSE_QUEUE", "file_import_responses")
    snapshot_request_queue = os.getenv("SNAPSHOT_REQUESTS_QUEUE_NAME", "snapshot_requests")
    
    def consume_file_import_responses():
        """Consumer for A32 file import responses from S15."""
        try:
            with mq_lock:
                mq = MessageQueueService()
            
            mq.declare_queue(file_import_response_queue)
            
            # Set MQ service on file_import_service for sending requests
            file_import_service.set_mq_service(mq)
            
            logger.info(f"Starting A32 response consumer on queue: {file_import_response_queue}")
            
            mq.register_callback(
                file_import_response_queue,
                file_import_service.handle_import_response
            )
            mq.start_consuming()
        except Exception as e:
            logger.error(f"A32 response consumer error: {e}")
    
    def consume_snapshot_requests():
        """Consumer for A33 snapshot requests from S12."""
        try:
            with mq_lock:
                mq = MessageQueueService()
            
            mq.declare_queue(snapshot_request_queue)
            
            # Set MQ service on snapshot_service for sending responses
            snapshot_service.set_mq_service(mq)
            
            logger.info(f"Starting A33 request consumer on queue: {snapshot_request_queue}")
            
            mq.register_callback(
                snapshot_request_queue,
                snapshot_service.handle_snapshot_request
            )
            mq.start_consuming()
        except Exception as e:
            logger.error(f"A33 request consumer error: {e}")
    
    # Start consumer threads
    threads = [
        threading.Thread(target=consume_file_import_responses, daemon=True, name="A32-Consumer"),
        threading.Thread(target=consume_snapshot_requests, daemon=True, name="A33-Consumer"),
    ]
    
    for t in threads:
        t.start()
        logger.info(f"Started thread: {t.name}")
    
    return threads


def setup_file_import_mq_sender():
    """
    Set up a separate MQ connection for sending file import requests to S15.
    This is needed because the consumer threads use their own connections.
    """
    from .services.MessageQueueService import MessageQueueService
    from .services import file_import_service
    
    try:
        mq = MessageQueueService()
        file_import_service.set_mq_service(mq)
        logger.info("Set up MQ sender for file import requests")
    except Exception as e:
        logger.warning(f"Could not set up MQ sender: {e}")


def main():
    """Main entry point."""
    from . import app, socketio
    
    # Get Flask configuration from environment
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "7011"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting S11 Partner Local Knowledge Service")
    logger.info(f"HTTP API will be available at http://{host}:{port}")
    
    # Start RabbitMQ consumers
    try:
        consumer_threads = start_rabbitmq_consumers()
        logger.info(f"Started {len(consumer_threads)} RabbitMQ consumer threads")
    except Exception as e:
        logger.warning(f"Could not start RabbitMQ consumers: {e}")
        logger.warning("Service will run without RabbitMQ functionality")
    
    # Set up MQ sender for file imports
    setup_file_import_mq_sender()
    
    # Start Flask server with SocketIO
    logger.info(f"Starting Flask server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
