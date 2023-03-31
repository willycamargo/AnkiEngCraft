import sys
import io
import os
import csv
import unittest
import tempfile
from unittest.mock import patch, MagicMock, call
from azure.cognitiveservices.speech import ResultReason
from anki_poly import read_input_file, write_csv_file, create_anki_deck, create_cards_in_parallel, create_card, get_speech_config_with_random_voice, generate_audio, anki_poly, Translator

OUTPUT_DIR = 'output'
AUDIO_OUTPUT_DIR = f'{OUTPUT_DIR}/audio'

class TestAnkiDeckCreator(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and change the working directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = os.path.join(self.temp_dir.name, "output")
        self.audio_output_dir = os.path.join(self.output_dir, "audio")

        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audio_output_dir, exist_ok=True)

        # Suppress print logs
        self.original_stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        # Remove output directory after tests
        self.temp_dir.cleanup()
        # Restore original stdout
        sys.stdout = self.original_stdout

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

    @patch("anki_poly.cpu_count")
    @patch("anki_poly.Pool")
    @patch("anki_poly.partial")
    def test_create_cards_in_parallel(self, mock_partial, mock_pool, mock_cpu_count):
        sentences = ["Test sentence", "Another test sentence"]

        # Mock the cpu_count function
        mock_cpu_count.return_value = 4

        # Mock the card returned by create_card
        mock_card = {
            "Front": "Test sentence",
            "Back": "translated",
            "AudioPath": "output/audio/test-sentence.mp3",
            "AudioTag": "[sound:test-sentence.mp3]",
        }

        # Mock the map function of the pool
        pool_instance = mock_pool.return_value.__enter__.return_value
        pool_instance.map.return_value = [mock_card] * len(sentences)

        cards = create_cards_in_parallel(sentences)

        # Check if the functions were called properly
        mock_cpu_count.assert_called_once()
        mock_pool.assert_called_once_with(mock_cpu_count.return_value)
        mock_partial.assert_called_once_with(create_card)

        self.assertEqual(len(cards), len(sentences))
        self.assertTrue(all([card["Back"] == "translated" for card in cards]))

    @patch("anki_poly.Translator")
    @patch("anki_poly.generate_audio")
    def test_create_card(self, mock_generate_audio, mock_translator):
        sentence = "Hello, World!"
        translated_text = "Olá, Mundo!"
        audio_file_name = "hello-world"
        audio_file_path = f"{self.audio_output_dir}/{audio_file_name}.mp3"
        
        mock_translation = MagicMock()
        mock_translation.text = translated_text
        mock_translator_instance = MagicMock()
        mock_translator_instance.translate.return_value = mock_translation
        mock_translator.return_value = mock_translator_instance
        mock_generate_audio.return_value = (audio_file_name, audio_file_path)
        
        expected_card = {
            "Front": sentence,
            "Back": translated_text,
            "AudioTag": f"[sound:{audio_file_name}.mp3]",
            "AudioPath": audio_file_path
        }
        
        # Act
        result_card = create_card(sentence)
        
        # Assert
        self.assertEqual(result_card, expected_card)
        mock_translator_instance.translate.assert_called_once_with(sentence, src='en', dest='pt')
        mock_generate_audio.assert_called_once_with(sentence)
    
    @patch("anki_poly.SpeechConfig")
    def test_get_speech_config_with_random_voice(self, mock_speech_config):
        speech_config = get_speech_config_with_random_voice()
        self.assertIsNotNone(speech_config)
        self.assertEqual(speech_config.speech_synthesis_language, "en-US")
        self.assertTrue(speech_config.speech_synthesis_voice_name.startswith("en-US-"))
    
    @patch("anki_poly.get_speech_config_with_random_voice")
    @patch("anki_poly.SpeechSynthesizer")
    @patch("anki_poly.AudioConfig")
    def test_generate_audio(self, mock_audio_config, mock_speech_synthesizer, mock_get_speech_config):
        # Arrange
        text = "Hello, World!"
        audio_file_name = "hello-world"
        audio_file_path = f"{self.audio_output_dir}/{audio_file_name}.mp3"

        # Mock result object
        mock_result = MagicMock()
        mock_result.reason = ResultReason.SynthesizingAudioCompleted

        # Mock speech config
        mock_speech_config = MagicMock()
        mock_get_speech_config.return_value = mock_speech_config

        # Mock synthesizer object
        mock_synthesizer_instance = MagicMock()
        mock_synthesizer_instance.speak_text.return_value = mock_result
        mock_speech_synthesizer.return_value = mock_synthesizer_instance

        # Act
        result_file_name, result_file_path = generate_audio(text, audio_output_dir=self.audio_output_dir)

        # Assert
        self.assertEqual(result_file_name, audio_file_name)
        self.assertEqual(result_file_path, audio_file_path)
        mock_audio_config.assert_called_once_with(filename=audio_file_path)
        mock_speech_synthesizer.assert_called_once_with(speech_config=mock_speech_config, audio_config=mock_audio_config.return_value)
        mock_synthesizer_instance.speak_text.assert_called_once_with(text)
    
    @patch("anki_poly.read_input_file")
    @patch("anki_poly.create_cards_in_parallel")
    @patch("anki_poly.create_anki_deck")
    @patch("anki_poly.write_csv_file")
    def test_anki_poly(self, mock_write_csv_file, mock_create_anki_deck, mock_create_cards_in_parallel, mock_read_input_file):
        input_file = "input.csv"
        output_file_name = "output"
        output_format = "anki"
        
        # Mock input sentences and generated cards
        sentences = ["Hello, World!", "How are you?"]
        cards = [{"Front": "Hello, World!", "Back": "Olá, Mundo!"}, {"Front": "How are you?", "Back": "Como você está?"}]
        
        mock_read_input_file.return_value = sentences
        mock_create_cards_in_parallel.return_value = cards

        # Call anki_poly
        anki_poly(input_file, output_file_name, output_format)

        # Check if called functions are correct
        mock_read_input_file.assert_called_once_with(input_file)
        mock_create_cards_in_parallel.assert_called_once_with(sentences)
        mock_create_anki_deck.assert_called_once_with(output_file_name, cards, f"{OUTPUT_DIR}/{output_file_name}.apkg")
        mock_write_csv_file.assert_not_called()



if __name__ == "__main__":
    unittest.main()
