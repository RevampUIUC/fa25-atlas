import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)


class MongoDatabase:
    """MongoDB connection and operations handler"""

    def __init__(self, connection_string: str = None, database_name: str = "atlas"):
        """
        Initialize MongoDB connection

        Args:
            connection_string: MongoDB connection string
            database_name: Database name
        """
        self.connection_string = connection_string or os.getenv("MONGO_URI")
        self.database_name = database_name or os.getenv("MONGO_DB", "atlas")

        if not self.connection_string:
            raise ValueError("Missing MONGO_URI configuration")

        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.database_name]
            # Test connection
            self.client.admin.command("ping")
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            self._create_indexes()
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def _create_indexes(self):
        """Create necessary database indexes"""
        try:
            # Users collection indexes
            if "users" in self.db.list_collection_names():
                self.db.users.create_index([("email", ASCENDING)], unique=True)
                self.db.users.create_index([("phone_number", ASCENDING)])

            # Calls collection indexes
            if "calls" in self.db.list_collection_names():
                self.db.calls.create_index([("user_id", ASCENDING)])
                self.db.calls.create_index([("twilio_sid", ASCENDING)], unique=True)
                self.db.calls.create_index([("created_at", DESCENDING)])
                self.db.calls.create_index([("status", ASCENDING)])

            # Recordings collection indexes
            if "recordings" in self.db.list_collection_names():
                self.db.recordings.create_index([("call_id", ASCENDING)])
                self.db.recordings.create_index([("twilio_sid", ASCENDING)])

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Could not create indexes: {str(e)}")

    def close(self):
        """Close database connection"""
        self.client.close()
        logger.info("MongoDB connection closed")

    # User operations
    def create_user(self, user_data: Dict[str, Any]) -> str:
        """
        Create a new user

        Args:
            user_data: User data dictionary

        Returns:
            User ID
        """
        try:
            user_data["created_at"] = datetime.utcnow()
            user_data["updated_at"] = datetime.utcnow()
            result = self.db.users.insert_one(user_data)
            logger.info(f"User created: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            raise

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID

        Args:
            user_id: User ID

        Returns:
            User document or None
        """
        try:
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if user:
                user["id"] = str(user["_id"])
                del user["_id"]
            return user
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {str(e)}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email

        Args:
            email: User email

        Returns:
            User document or None
        """
        try:
            user = self.db.users.find_one({"email": email})
            if user:
                user["id"] = str(user["_id"])
                del user["_id"]
            return user
        except Exception as e:
            logger.error(f"Failed to get user by email: {str(e)}")
            return None

    def list_users(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        List all users with pagination

        Args:
            page: Page number
            page_size: Page size

        Returns:
            Dict with total, page, page_size, and users list
        """
        try:
            skip = (page - 1) * page_size
            total = self.db.users.count_documents({})
            users = list(
                self.db.users.find()
                .sort("created_at", DESCENDING)
                .skip(skip)
                .limit(page_size)
            )

            for user in users:
                user["id"] = str(user["_id"])
                del user["_id"]

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "data": users,
            }
        except Exception as e:
            logger.error(f"Failed to list users: {str(e)}")
            raise

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update user

        Args:
            user_id: User ID
            update_data: Data to update

        Returns:
            True if successful
        """
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {str(e)}")
            raise

    def delete_user(self, user_id: str) -> bool:
        """
        Delete user

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            result = self.db.users.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {str(e)}")
            raise

    # Call operations
    def create_call(self, call_data: Dict[str, Any]) -> str:
        """
        Create a new call record

        Args:
            call_data: Call data dictionary

        Returns:
            Call ID
        """
        try:
            call_data["created_at"] = datetime.utcnow()
            call_data["updated_at"] = datetime.utcnow()
            result = self.db.calls.insert_one(call_data)
            logger.info(f"Call created: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create call: {str(e)}")
            raise

    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        Get call by ID

        Args:
            call_id: Call ID

        Returns:
            Call document or None
        """
        try:
            call = self.db.calls.find_one({"_id": ObjectId(call_id)})
            if call:
                call["id"] = str(call["_id"])
                del call["_id"]
            return call
        except Exception as e:
            logger.error(f"Failed to get call {call_id}: {str(e)}")
            return None

    def get_call_by_twilio_sid(self, twilio_sid: str) -> Optional[Dict[str, Any]]:
        """
        Get call by Twilio SID

        Args:
            twilio_sid: Twilio Call SID

        Returns:
            Call document or None
        """
        try:
            call = self.db.calls.find_one({"twilio_sid": twilio_sid})
            if call:
                call["id"] = str(call["_id"])
                del call["_id"]
            return call
        except Exception as e:
            logger.error(f"Failed to get call by Twilio SID: {str(e)}")
            return None

    def list_user_calls(
        self, user_id: str, page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """
        List calls for a specific user

        Args:
            user_id: User ID
            page: Page number
            page_size: Page size

        Returns:
            Dict with total, page, page_size, and calls list
        """
        try:
            skip = (page - 1) * page_size
            total = self.db.calls.count_documents({"user_id": user_id})
            calls = list(
                self.db.calls.find({"user_id": user_id})
                .sort("created_at", DESCENDING)
                .skip(skip)
                .limit(page_size)
            )

            for call in calls:
                call["id"] = str(call["_id"])
                del call["_id"]

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "data": calls,
            }
        except Exception as e:
            logger.error(f"Failed to list calls for user {user_id}: {str(e)}")
            raise

    def update_call(self, call_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update call record

        Args:
            call_id: Call ID
            update_data: Data to update

        Returns:
            True if successful
        """
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = self.db.calls.update_one(
                {"_id": ObjectId(call_id)}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update call {call_id}: {str(e)}")
            raise

    def update_call_by_twilio_sid(
        self, twilio_sid: str, update_data: Dict[str, Any]
    ) -> bool:
        """
        Update call by Twilio SID

        Args:
            twilio_sid: Twilio Call SID
            update_data: Data to update

        Returns:
            True if successful
        """
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = self.db.calls.update_one(
                {"twilio_sid": twilio_sid}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update call by Twilio SID: {str(e)}")
            raise

    # Recording operations
    def create_recording(self, recording_data: Dict[str, Any]) -> str:
        """
        Create a new recording record

        Args:
            recording_data: Recording data dictionary

        Returns:
            Recording ID
        """
        try:
            recording_data["created_at"] = datetime.utcnow()
            result = self.db.recordings.insert_one(recording_data)
            logger.info(f"Recording created: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create recording: {str(e)}")
            raise

    def get_recording(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recording by ID

        Args:
            recording_id: Recording ID

        Returns:
            Recording document or None
        """
        try:
            recording = self.db.recordings.find_one({"_id": ObjectId(recording_id)})
            if recording:
                recording["id"] = str(recording["_id"])
                del recording["_id"]
            return recording
        except Exception as e:
            logger.error(f"Failed to get recording {recording_id}: {str(e)}")
            return None

    def get_recording_by_call_id(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recording by call ID

        Args:
            call_id: Call ID

        Returns:
            Recording document or None
        """
        try:
            recording = self.db.recordings.find_one({"call_id": call_id})
            if recording:
                recording["id"] = str(recording["_id"])
                del recording["_id"]
            return recording
        except Exception as e:
            logger.error(f"Failed to get recording for call {call_id}: {str(e)}")
            return None

    def update_recording(
        self, recording_id: str, update_data: Dict[str, Any]
    ) -> bool:
        """
        Update recording record

        Args:
            recording_id: Recording ID
            update_data: Data to update

        Returns:
            True if successful
        """
        try:
            result = self.db.recordings.update_one(
                {"_id": ObjectId(recording_id)}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update recording {recording_id}: {str(e)}")
            raise

    def list_call_recordings(self, call_id: str) -> List[Dict[str, Any]]:
        """
        List all recordings for a call

        Args:
            call_id: Call ID

        Returns:
            List of recording documents
        """
        try:
            recordings = list(self.db.recordings.find({"call_id": call_id}))
            for recording in recordings:
                recording["id"] = str(recording["_id"])
                del recording["_id"]
            return recordings
        except Exception as e:
            logger.error(f"Failed to list recordings for call {call_id}: {str(e)}")
            raise

#starting from here
    def ensure_track1_indexes(self) -> None:
        """Indexes required by Track-1 spec (idempotent)."""
        self.db.users.create_index([("external_id", ASCENDING)], unique=True, name="uniq_external_id")
        self.db.users.create_index([("phone", ASCENDING)], name="idx_phone")
        self.db.calls.create_index([("call_sid", ASCENDING)], unique=True, name="uniq_call_sid")
        self.db.calls.create_index([("user_id", ASCENDING), ("started_at", ASCENDING)],
                                name="idx_user_started_at")
        self.db.transcripts.create_index([("call_sid", ASCENDING)], name="idx_call_sid")


    def upsert_user(self, external_id: str, phone: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create/update user by external_id; also store phone."""
        payload: Dict[str, Any] = {"external_id": external_id, "phone": phone, "updated_at": datetime.utcnow()}
        if name:
            payload["name"] = name
        self.db.users.update_one({"external_id": external_id},
                                {"$set": payload, "$setOnInsert": {"created_at": datetime.utcnow()}},
                                upsert=True)
        doc = self.db.users.find_one({"external_id": external_id})
        if doc:
            doc["id"] = str(doc["_id"]); del doc["_id"]
        return doc

    def create_call(self, user_id: str, call_sid: str, started_at: datetime) -> str:
        """Create call with required fields; unique on call_sid."""
        existing = self.db.calls.find_one({"call_sid": call_sid})
        if existing:
            return str(existing["_id"])
        doc = {
            "user_id": user_id,           
            "call_sid": call_sid,
            "started_at": started_at,
            "status": "in-progress",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        doc.setdefault("twilio_sid", call_sid)
        res = self.db.calls.insert_one(doc)
        return str(res.inserted_id)

    def update_call_status(self,
                        call_sid: str,
                        status: Optional[str] = None,
                        duration_sec: Optional[int] = None,
                        ended_at: Optional[datetime] = None,
                        meta: Optional[Dict[str, Any]] = None) -> bool:
        """Update call by call_sid."""
        update: Dict[str, Any] = {"updated_at": datetime.utcnow()}
        if status is not None: update["status"] = status
        if duration_sec is not None: update["duration_sec"] = duration_sec
        if ended_at is not None: update["ended_at"] = ended_at
        if meta is not None: update["meta"] = meta
        r = self.db.calls.update_one({"call_sid": call_sid}, {"$set": update}, upsert=True)
        return bool(r.matched_count or r.upserted_id)

    def save_recording(self, call_sid: str, recording_url: str, transcription_text: Optional[str] = None) -> bool:
        """Store recording URL + optional transcription on the call doc."""
        r = self.db.calls.update_one(
            {"call_sid": call_sid},
            {"$set": {
                "recording_url": recording_url,
                "transcription_text": transcription_text,
                "recording_saved_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }},
            upsert=True
        )
        return bool(r.matched_count or r.upserted_id)

    def save_transcript(self, call_sid: str, speaker: str, text: str, ts: datetime) -> str:
        """Append one transcript row."""
        doc = {"call_sid": call_sid, "speaker": speaker, "text": text, "ts": ts, "created_at": datetime.utcnow()}
        res = self.db.transcripts.insert_one(doc)
        return str(res.inserted_id)

