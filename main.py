# This script creates Anki decks or CSV files from a CSV input file,
# translating the sentences and generating audio using Azure Speech API.
import os
import csv
import argparse
import genanki
import time
import random
from loguru import logger
from dotenv import load_dotenv
from functools import partial
from googletrans import Translator
from multiprocessing import Pool, cpu_count
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason, SpeechSynthesisCancellationDetails
from slugify import slugify

# Load environment variables from the .env file
load_dotenv()

# Get Azure Speech API credentials from environment variables
azure_speech_key = os.getenv('AZURE_SPEECH_KEY')
azure_service_region = os.getenv('AZURE_REGION')

# Anki Static IDs
anki_model_id = int(os.getenv('ANKI_MODEL_ID'))
anki_deck_id = int(os.getenv('ANKI_DECK_ID'))

OUTPUT_DIR = os.getenv('OUTPUT_DIR')
AUDIO_OUTPUT_DIR = f'{OUTPUT_DIR}/audio'

# Reads data from a file and returns a list of dictionaries.
def read_input_file(file_name):
    logger.info('Reading input file.')
    _, file_extension = os.path.splitext(file_name)

    if file_extension.lower() == '.csv':
        with open(file_name, 'r') as f:
            reader = csv.DictReader(f)
            try:
                csv_data = list(reader)
                if 'sentence' in csv_data[0]:
                    sentences = [d['sentence'] for d in csv_data if d['sentence'].strip()]
                else:
                    raise ValueError('CSV file does not contain a "sentence" column.')
            except csv.Error as e:
                raise ValueError('File is not a valid CSV.') from e
    else:
        with open(file_name, 'r') as f:
            sentences = [line for line in f.read().splitlines() if line.strip()]

    return sentences

# Writes a list of dictionaries to a CSV file
def write_csv_file(file_name, cards):
    logger.info('Writing CSV file.')
    keys = cards[0].keys()
    with open(file_name, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(cards)

# Creates an Anki deck from a list of card data, and saves it to an .apkg file.
def create_anki_deck(deck_name, cards, output_file):
    logger.info('Creating Anki deck.')

    # Define the Anki model
    model = genanki.Model(
        model_id=anki_model_id,
        name='PolyAnki',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
            {'name': 'Audio'},
        ],
        templates=[
            {
                'name': 'english-text-audio',
                'qfmt': '<div style="text-align: center;">{{Front}}<br />{{Audio}}</div>',
                'afmt': '<div style="text-align: center;">{{FrontSide}}<hr id="answer">{{Back}}</div>',
            },
        ])

    # Create the deck
    deck = genanki.Deck(
        deck_id=anki_deck_id,
        name=deck_name)

    # Add notes (cards) to the deck and collect audio file paths
    logger.info('Adding notes to the Anki deck.')
    media_files = []
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[card['Front'], card['Back'], card.get('AudioTag', '')])
        deck.add_note(note)
        media_files.append(f"{card['AudioPath']}")

    # Save the deck to a file with attached media files
    genanki.Package(deck, media_files=media_files).write_to_file(output_file)
    logger.info(f"Anki deck saved as {output_file}")

# Translates a list of sentences and creates a list of cards with translations and audio tags
def create_cards_in_parallel(sentences):
    logger.info('Initializing translation.')
    with Pool(cpu_count()) as pool:
        cards = pool.map(partial(create_card), sentences)
    return cards

# Translates a sentence, generates an audio tag, and creates a card with the translation and audio
def create_card(sentence):
    logger.info(f'Creating card for "{sentence}".')
    sentence_translated = translate(sentence)
    audio_file_name, audio_file_path  = generate_audio(sentence) 
    
    card = {
        "Front": sentence,
        "Back": sentence_translated,
        "AudioTag": f"[sound:{audio_file_name}.mp3]",
        "AudioPath": audio_file_path
    }

    return card

# Translate text
def translate(text, src='en', dest='pt'):
    translator = Translator()
    translation = translator.translate(text, src=src, dest=dest)
    return translation.text

# Generates the SpeechConfig with a random voice
def get_speech_config_with_random_voice():
    # Available English US voices
    english_us_voices = [
        "en-US-AmberNeural",
        "en-US-AnaNeural",
        "en-US-AriaNeural",
        "en-US-AshleyNeural",
        "en-US-BrandonNeural",
        "en-US-ChristopherNeural",
        "en-US-CoraNeural",
        "en-US-DavisNeural",
        "en-US-ElizabethNeural",
        "en-US-EricNeural",
        "en-US-GuyNeural",
        "en-US-JacobNeural",
        "en-US-JaneNeural",
        "en-US-JasonNeural",
        "en-US-JennyNeural",
        "en-US-MichelleNeural",
        "en-US-MonicaNeural",
        "en-US-NancyNeural",
        "en-US-SaraNeural",
        "en-US-SteffanNeural",
        "en-US-TonyNeural",
    ]

    # Choose a random English US voice
    random_voice = random.choice(english_us_voices)
    speech_config = SpeechConfig(subscription=azure_speech_key, region=azure_service_region)
    speech_config.speech_synthesis_language = "en-US"
    speech_config.speech_synthesis_voice_name = random_voice

    return speech_config

# Generates an audio for a given text using Azure Speech API and saves the audio file as an MP3
MAX_RETRIES_TO_GENERATE_AUDIO = 5
def generate_audio(text, audio_output_dir=AUDIO_OUTPUT_DIR):
    audio_file_name = slugify(text)
    audio_file_path = f"{audio_output_dir}/{audio_file_name}.mp3"
    logger.info(f"Checking if audio file {audio_file_path} exists.")

    for i in range(MAX_RETRIES_TO_GENERATE_AUDIO):
        if not os.path.exists(audio_file_path):
            logger.info(f"File {audio_file_path} does not exist, creating file using Azure Speech API.")
            audio_config = AudioConfig(filename=audio_file_path)
            speech_config = get_speech_config_with_random_voice()
            synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_text(text)
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                logger.info("Audio file created successfully.")
                break
            elif result.reason == ResultReason.Canceled:
                cancellation_details = SpeechSynthesisCancellationDetails(result)
                logger.error(f"Speech synthesis was canceled. Reason: {cancellation_details.reason}")
                if cancellation_details.error_details:
                    logger.error(f"Error details: {cancellation_details.error_details}")
                
                # Remove the file and retry
                os.remove(audio_file_path)
        else:
            break
    else:
        raise Exception(f"Failed to create audio file {audio_file_path} after {MAX_RETRIES_TO_GENERATE_AUDIO} retries.")

    return [audio_file_name, audio_file_path]

# Reads an input file, generates translated cards with audio,
# and creates either an Anki deck or a CSV file based on the specified output format.
def main(input_file, output_file_name, output_format):
    # Create necessary directories
    os.makedirs(f"{OUTPUT_DIR}", exist_ok=True)
    os.makedirs(f"{AUDIO_OUTPUT_DIR}", exist_ok=True)

    # Read input file
    sentences = read_input_file(input_file)

    # Generate translated cards
    cards = create_cards_in_parallel(sentences)

    # Write output file
    if output_format == 'anki':
        create_anki_deck(output_file_name, cards, f"{OUTPUT_DIR}/{output_file_name}.apkg")
    elif output_format == 'csv':
        write_csv_file(f'{OUTPUT_DIR}/{output_file_name}.csv', cards)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Create Anki decks or CSV files from a CSV input file.')
    parser.add_argument('--input', help='The input file path')
    parser.add_argument('--format', choices=['anki', 'csv'], default='anki', help='The output format (default: anki)')
    parser.add_argument('--output', help='The output file name')
    args = parser.parse_args()

    input_file = args.input
    output_file_name = os.path.splitext(args.output if args.output else input_file)[0]
    output_format = args.format
    start_time = time.time()
    main(input_file, output_file_name, output_format)
    num_cards = len(read_input_file(input_file))
    end_time = time.time()
    time_taken = end_time - start_time
    logger.info(f"Generated {num_cards} cards in {time_taken:.2f} seconds.")
