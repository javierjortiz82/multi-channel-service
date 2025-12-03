"""Unit tests for the input classifier service."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from telegram_bot.services.input_classifier import InputClassifier, InputType


class TestInputType:
    """Tests for InputType enum."""

    def test_input_type_values(self) -> None:
        """Verify all expected input types exist."""
        expected_types = [
            "text",
            "command",
            "photo",
            "document",
            "video",
            "audio",
            "voice",
            "video_note",
            "sticker",
            "animation",
            "location",
            "venue",
            "contact",
            "poll",
            "dice",
            "unknown",
        ]
        actual_values = [t.value for t in list(InputType)]
        for type_value in expected_types:
            assert type_value in actual_values

    def test_input_type_is_str_enum(self) -> None:
        """Verify InputType is a str subclass."""
        assert InputType.TEXT.value == "text"
        assert InputType.PHOTO.value == "photo"
        # Verify str inheritance
        assert isinstance(InputType.TEXT, str)


class TestInputClassifier:
    """Tests for InputClassifier class."""

    @pytest.fixture
    def classifier(self) -> InputClassifier:
        """Create classifier instance."""
        return InputClassifier()

    def test_classify_text_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of plain text message."""
        mock_message.text = "Hello, world!"
        result = classifier.classify(mock_message)
        assert result == InputType.TEXT

    def test_classify_command_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of command message."""
        mock_message.text = "/start"
        result = classifier.classify(mock_message)
        assert result == InputType.COMMAND

    def test_classify_photo_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of photo message."""
        mock_message.photo = [MagicMock()]
        result = classifier.classify(mock_message)
        assert result == InputType.PHOTO

    def test_classify_document_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of document message."""
        mock_message.document = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.DOCUMENT

    def test_classify_video_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of video message."""
        mock_message.video = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.VIDEO

    def test_classify_audio_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of audio message."""
        mock_message.audio = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.AUDIO

    def test_classify_voice_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of voice message."""
        mock_message.voice = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.VOICE

    def test_classify_video_note_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of video note message."""
        mock_message.video_note = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.VIDEO_NOTE

    def test_classify_sticker_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of sticker message."""
        mock_message.sticker = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.STICKER

    def test_classify_animation_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of animation message."""
        mock_message.animation = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.ANIMATION

    def test_classify_location_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of location message."""
        mock_message.location = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.LOCATION

    def test_classify_venue_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of venue message."""
        mock_message.venue = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.VENUE

    def test_classify_contact_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of contact message."""
        mock_message.contact = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.CONTACT

    def test_classify_poll_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of poll message."""
        mock_message.poll = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.POLL

    def test_classify_dice_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of dice message."""
        mock_message.dice = MagicMock()
        result = classifier.classify(mock_message)
        assert result == InputType.DICE

    def test_classify_unknown_message(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test classification of unknown message type."""
        result = classifier.classify(mock_message)
        assert result == InputType.UNKNOWN

    def test_classify_caption_as_text(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test that message with only caption is classified as text."""
        mock_message.caption = "A caption"
        result = classifier.classify(mock_message)
        assert result == InputType.TEXT


class TestInputClassifierRaw:
    """Tests for classify_raw method."""

    @pytest.fixture
    def classifier(self) -> InputClassifier:
        """Create classifier instance."""
        return InputClassifier()

    def test_classify_raw_text(self, classifier: InputClassifier) -> None:
        """Test raw classification of text message."""
        data: dict[str, Any] = {"text": "Hello"}
        result = classifier.classify_raw(data)
        assert result == InputType.TEXT

    def test_classify_raw_command(self, classifier: InputClassifier) -> None:
        """Test raw classification of command message."""
        data: dict[str, Any] = {"text": "/start"}
        result = classifier.classify_raw(data)
        assert result == InputType.COMMAND

    def test_classify_raw_photo(self, classifier: InputClassifier) -> None:
        """Test raw classification of photo message."""
        data: dict[str, Any] = {"photo": [{"file_id": "123"}]}
        result = classifier.classify_raw(data)
        assert result == InputType.PHOTO

    def test_classify_raw_document(self, classifier: InputClassifier) -> None:
        """Test raw classification of document message."""
        data: dict[str, Any] = {"document": {"file_id": "123"}}
        result = classifier.classify_raw(data)
        assert result == InputType.DOCUMENT

    def test_classify_raw_location(self, classifier: InputClassifier) -> None:
        """Test raw classification of location message."""
        data: dict[str, Any] = {"location": {"latitude": 0, "longitude": 0}}
        result = classifier.classify_raw(data)
        assert result == InputType.LOCATION

    def test_classify_raw_unknown(self, classifier: InputClassifier) -> None:
        """Test raw classification of empty message."""
        data: dict[str, Any] = {}
        result = classifier.classify_raw(data)
        assert result == InputType.UNKNOWN

    def test_classify_raw_caption(self, classifier: InputClassifier) -> None:
        """Test raw classification with caption."""
        data: dict[str, Any] = {"caption": "A caption"}
        result = classifier.classify_raw(data)
        assert result == InputType.TEXT


class TestInputClassifierUserInfo:
    """Tests for user info extraction."""

    @pytest.fixture
    def classifier(self) -> InputClassifier:
        """Create classifier instance."""
        return InputClassifier()

    def test_get_user_info_with_username(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test user info extraction with username."""
        mock_message.text = "Test"
        classifier.classify(mock_message)
        # Just verify no exceptions are raised

    def test_get_user_info_without_username(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test user info extraction without username."""
        mock_message.text = "Test"
        mock_message.from_user.username = None
        classifier.classify(mock_message)
        # Just verify no exceptions are raised

    def test_get_user_info_no_user(
        self, classifier: InputClassifier, mock_message: MagicMock
    ) -> None:
        """Test user info extraction with no user."""
        mock_message.text = "Test"
        mock_message.from_user = None
        classifier.classify(mock_message)
        # Just verify no exceptions are raised
