"""
File Imports Controller for H28 API.
Handles file import operations for telecom knowledge extraction.
"""

from flask import request, url_for
from flask_restx import Namespace, Resource, fields, abort
from werkzeug.datastructures import FileStorage
from ...utils.pageable import Pageable
from ...utils.hateoas import HATEOAS
from ...utils.db import serialize_mongo_doc
from ...services.JWTAuthService import require_auth

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('local-knowledge/file-imports', description='Quản lý file import dữ liệu kiến thức viễn thông')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# Package fields for nested use
package_fields = {
    "Mã dịch vụ": fields.String(description="Mã dịch vụ gói cước"),
    "Thời gian thanh toán": fields.String(description="Trả trước/trả sau"),
    "Các dịch vụ tiên quyết": fields.String(description="Các dịch vụ cần có"),
    "Giá (VNĐ)": fields.Integer(description="Giá gói cước (VNĐ)"),
    "Chu kỳ (ngày)": fields.Integer(description="Chu kỳ gói cước (ngày)"),
    "4G tốc độ tiêu chuẩn/ngày": fields.Float(description="Dung lượng 4G tốc độ tiêu chuẩn mỗi ngày (GB)"),
    "4G tốc độ cao/ngày": fields.Float(description="Dung lượng 4G tốc độ cao mỗi ngày (GB)"),
    "4G tốc độ tiêu chuẩn/chu kỳ": fields.Float(description="Dung lượng 4G tốc độ tiêu chuẩn mỗi chu kỳ (GB)"),
    "4G tốc độ cao/chu kỳ": fields.Float(description="Dung lượng 4G tốc độ cao mỗi chu kỳ (GB)"),
    "Gọi nội mạng": fields.String(description="Thông tin gọi nội mạng"),
    "Gọi ngoại mạng": fields.String(description="Thông tin gọi ngoại mạng"),
    "Tin nhắn": fields.String(description="Thông tin tin nhắn"),
    "Chi tiết": fields.String(description="Thông tin chi tiết gói cước"),
    "Tự động gia hạn": fields.String(description="Thông tin tự động gia hạn"),
    "Cú pháp đăng ký": fields.String(description="Cú pháp đăng ký gói cước"),
}

package_model = api.model("ExtractedPackage", package_fields)

file_import_list_dto = api.model("FileImportList", {
    "id": fields.String(readonly=True, description="ID của file import"),
    "file_name": fields.String(description="Tên file"),
    "status": fields.String(description="Trạng thái: PENDING, EXTRACTED, FAILED, APPROVED, REJECTED"),
    "created_at": fields.String(description="Thời điểm tạo"),
})

file_import_detail_dto = api.model("FileImportDetail", {
    "id": fields.String(readonly=True, description="ID của file import"),
    "file_name": fields.String(description="Tên file"),
    "status": fields.String(description="Trạng thái"),
    "error_message": fields.String(description="Thông báo lỗi (nếu có)"),
    "created_at": fields.String(description="Thời điểm tạo"),
    "packages": fields.List(fields.Nested(package_model), description="Danh sách gói cước trích xuất"),
})

file_import_create_response_dto = api.model("FileImportCreateResponse", {
    "id": fields.String(description="ID của file import task"),
    "message": fields.String(description="Thông báo"),
})

file_import_action_response_dto = api.model("FileImportActionResponse", {
    "id": fields.String(description="ID của file import"),
    "message": fields.String(description="Thông báo kết quả"),
})

packages_update_dto = api.model("PackagesUpdate", {
    "packages": fields.List(fields.Nested(package_model), description="Danh sách gói cước đã chỉnh sửa"),
})

# File upload parser
upload_parser = api.parser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='File to import')
upload_parser.add_argument('metadata', location='form', type=str, required=False, help='JSON metadata with file_name')

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import file_import_service
import json

###################################
## STEP 4. DEFINE THE CONTROLLER ##
###################################

h = HATEOAS(api)

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.xlsx', '.xls', '.docx'}


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    import os
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@api.route("/")
class FileImportCollection(Resource):
    service = file_import_service

    get_collection_qp = Pageable.pageable_query_params()

    @api.doc(description="Lấy danh sách các file imports (TP-13b).")
    @h.expect(get_collection_qp)
    @h.returns(
        file_import_list_dto,
        as_list=True,
        self_links=lambda content: [],
        collection_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_collection")],
    )
    @require_auth
    def get(self):
        args = self.get_collection_qp.parse_args()
        pageable = Pageable.from_query_params(args)
        return self.service.get_collection(pageable)

    @api.doc(description="Tải file dữ liệu kiến thức viễn thông lên hệ thống (TP-13a).")
    @api.expect(upload_parser)
    @api.response(202, 'File import initiated successfully')
    @require_auth
    def post(self):
        args = upload_parser.parse_args()
        uploaded_file = args['file']
        metadata_str = args.get('metadata', '{}')
        
        if not uploaded_file:
            abort(400, "No file provided")
        
        # Parse metadata
        try:
            metadata = json.loads(metadata_str) if metadata_str else {}
        except json.JSONDecodeError:
            metadata = {}
        
        # Get filename from metadata or from uploaded file
        file_name = metadata.get('file_name') or uploaded_file.filename or 'unknown'
        
        # Validate file extension
        if not allowed_file(file_name):
            abort(400, f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}")
        
        # Read file content
        file_content = uploaded_file.read()
        
        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            abort(400, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Create file import
        result = self.service.create_file_import(file_content, file_name)
        
        response = {
            "content": {
                "id": str(result["_id"]),
                "message": "File import initiated successfully"
            }
        }
        
        return response, 202


@api.route("/<string:id>")
class FileImportItem(Resource):
    service = file_import_service

    @api.doc(description="Lấy chi tiết file import (TP-13c).")
    @h.returns(
        file_import_detail_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_collection")],
    )
    @require_auth
    def get(self, id):
        result = self.service.get_item_by_id(id)
        return serialize_mongo_doc(result)


@api.route("/<string:id>/approve")
class FileImportApprove(Resource):
    service = file_import_service

    @api.doc(description="Approve file import - chấp nhận các gói cước trích xuất (TP-13e).")
    @h.returns(
        file_import_action_response_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_collection")],
    )
    @require_auth
    def post(self, id):
        result = self.service.approve_file_import(id)
        return {
            "id": str(result["_id"]),
            "message": "File import approved successfully"
        }


@api.route("/<string:id>/reject")
class FileImportReject(Resource):
    service = file_import_service

    @api.doc(description="Reject file import (TP-13f).")
    @h.returns(
        file_import_action_response_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_collection")],
    )
    @require_auth
    def post(self, id):
        result = self.service.reject_file_import(id)
        return {
            "id": str(result["_id"]),
            "message": "File import rejected successfully"
        }


@api.route("/<string:id>/packages")
class FileImportPackages(Resource):
    service = file_import_service

    @api.doc(description="Chỉnh sửa các gói cước trích xuất từ file import (TP-13d).")
    @api.expect(packages_update_dto)
    @h.returns(
        file_import_action_response_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/file-imports_file_import_collection")],
    )
    @require_auth
    def patch(self, id):
        data = request.get_json()
        packages = data.get('packages', [])
        result = self.service.update_extracted_packages(id, packages)
        return {
            "id": str(result["_id"]),
            "message": "Extracted packages updated successfully"
        }
