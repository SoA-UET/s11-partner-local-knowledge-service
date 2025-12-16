from .ConversationService import ConversationService
from .PackageService import PackageService
from .FAQService import FAQService
from .FileImportService import FileImportService
from .SnapshotService import SnapshotService
from .MessageQueueService import MessageQueueService
from ..collections import (
    conversations_collection,
    packages_collection,
    faqs_collection,
    file_imports_collection,
)

conversation_service = ConversationService(
    collection=conversations_collection,
)

# S11 Services
package_service = PackageService(
    collection=packages_collection,
)

faq_service = FAQService(
    collection=faqs_collection,
)

file_import_service = FileImportService(
    collection=file_imports_collection,
    packages_collection=packages_collection,
)

snapshot_service = SnapshotService(
    package_service=package_service,
    faq_service=faq_service,
)
