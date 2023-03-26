import os
import csv
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from anki_deck_creator import read_input_file, write_csv_file, create_anki_deck, generate_translated_cards, create_translated_card, generate_audio, Translator

class TestAnkiDeckCreator(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and change the working directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = os.path.join(self.temp_dir.name, "output")
        self.audio_output_dir = os.path.join(self.output_dir, "audio")
        
        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audio_output_dir, exist_ok=True)

    def tearDown(self):
        # Remove output directory after tests
        self.temp_dir.cleanup()

    def test_read_input_file_csv(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv") as temp_file:
            temp_file.write("sentence\nTest sentence\nAnother test sentence\n")
            temp_file.seek(0)
            sentences = read_input_file(temp_file.name)
            self.assertEqual(sentences, ["Test sentence", "Another test sentence"])

    def test_read_input_file_txt(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt") as temp_file:
            temp_file.write("Test sentence\nAnother test sentence\n")
            temp_file.seek(0)
            sentences = read_input_file(temp_file.name)
            self.assertEqual(sentences, ["Test sentence", "Another test sentence"])

    def test_write_csv_file(self):
        cards = [
            {"Front": "Test front", "Back": "Test back", "AudioTag": "[sound:test.mp3]"},
            {"Front": "Another front", "Back": "Another back", "AudioTag": "[sound:another.mp3]"},
        ]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv") as temp_file:
            write_csv_file(temp_file.name, cards)
            temp_file.seek(0)
            reader = csv.DictReader(temp_file)
            written_cards = list(reader)
            self.assertEqual(written_cards, cards)

    def test_create_anki_deck(self):
        cards = [
            {
                "Front": "Test",
                "Back": "Teste",
                "AudioPath": "test",
                "AudioTag": "[sound:test.mp3]"
            }
        ]
        output_file = os.path.join(self.output_dir, "Test_Deck.apkg")

        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(mode="wb", dir=self.audio_output_dir, delete=False) as temp_audio:
            temp_audio.write(b"Sample audio file")
            cards[0]["AudioPath"] = temp_audio.name
            cards[0]["AudioTag"] = f"[sound:{os.path.basename(temp_audio.name)}]"

            create_anki_deck("Test Deck", cards, output_file)
            self.assertTrue(os.path.exists(output_file))

        # Remove the temporary audio file
        os.remove(temp_audio.name)

    @patch("anki_deck_creator.cpu_count")
    @patch("anki_deck_creator.Pool")
    @patch("anki_deck_creator.partial")
    def test_generate_translated_cards(self, mock_partial, mock_pool, mock_cpu_count):
        sentences = ["Test sentence", "Another test sentence"]

        # Mock the cpu_count function
        mock_cpu_count.return_value = 4

        # Mock the card returned by create_translated_card
        mock_card = {
            "Front": "Test sentence",
            "Back": "translated",
            "AudioPath": "output/audio/test-sentence.mp3",
            "AudioTag": "[sound:test-sentence.mp3]",
        }

        # Mock the map function of the pool
        pool_instance = mock_pool.return_value.__enter__.return_value
        pool_instance.map.return_value = [mock_card] * len(sentences)

        cards = generate_translated_cards(sentences)

        # Check if the functions were called properly
        mock_cpu_count.assert_called_once()
        mock_pool.assert_called_once_with(mock_cpu_count.return_value)
        mock_partial.assert_called_once_with(create_translated_card)

        self.assertEqual(len(cards), len(sentences))
        self.assertTrue(all([card["Back"] == "translated" for card in cards]))

    @patch("anki_deck_creator.Translator")
    @patch("anki_deck_creator.SpeechSynthesizer")
    @patch("anki_deck_creator.SpeechConfig")
    def test_create_translated_card(self, mock_speech_config, mock_speech_synthesizer, mock_translator):
        sentence = "Test sentence"
        mock_translation = MagicMock()
        mock_translation.text = "translated"
        mock_translator.return_value.translate.return_value = mock_translation
        card = create_translated_card(sentence)
        self.assertEqual(card["Front"], sentence)
        self.assertEqual(card["Back"], "translated")
    
    @patch("anki_deck_creator.SpeechSynthesizer")
    @patch("anki_deck_creator.SpeechConfig")
    @patch("anki_deck_creator.AudioConfig")
    def test_generate_audio(self, mock_audio_config, mock_speech_config, mock_speech_synthesizer):
        text = "Test sentence"

        mock_speech_synthesizer.return_value.speak_text = MagicMock()
        _, audio_file_path = generate_audio(text, self.audio_output_dir)
        mock_audio_config.assert_called_once_with(filename=audio_file_path)
        mock_speech_synthesizer.assert_called_once()
        mock_speech_synthesizer.return_value.speak_text.assert_called_once_with(text)


if __name__ == "__main__":
    unittest.main()
