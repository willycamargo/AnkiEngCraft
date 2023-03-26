# This script creates Anki decks or CSV files from a CSV input file,
# translating the sentences and generating audio using Azure Speech API.
import os
import csv
import argparse
import genanki
import time
from dotenv import load_dotenv
from functools import partial
from googletrans import Translator
from multiprocessing import Pool, cpu_count
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig
from slugify import slugify

# Load environment variables from the .env file
load_dotenv()

# Get Azure Speech API credentials from environment variables
speech_key = os.getenv('AZURE_SPEECH_KEY')
service_region = os.getenv('AZURE_REGION')
speech_config = SpeechConfig(subscription=speech_key, region=service_region)

# Anki Static IDs
anki_model_id = int(os.getenv('ANKI_MODEL_ID'))
anki_deck_id = int(os.getenv('ANKI_DECK_ID'))

INPUT_DIR = 'input'
OUTPUT_DIR = 'output'
AUDIO_OUTPUT_DIR = f'{OUTPUT_DIR}/audio'

# Reads data from a file and returns a list of dictionaries.
def read_input_file(file_name):
    print('Reading input file.')
    _, file_extension = os.path.splitext(file_name)

    if file_extension.lower() == '.csv':
        with open(file_name, 'r') as f:
            reader = csv.DictReader(f)
            try:
                csv_data = list(reader)
                if 'sentence' in csv_data[0]:
                    sentences = [d['sentence'] for d in csv_data]
                else:
                    raise ValueError('CSV file does not contain a "sentence" column.')
            except csv.Error as e:
                raise ValueError('File is not a valid CSV.') from e
    else:
        with open(file_name, 'r') as f:
            sentences = f.read().splitlines()

    return sentences

# Writes a list of dictionaries to a CSV file
def write_csv_file(file_name, cards):
    print('Writing CSV file.')
    keys = cards[0].keys()
    with open(file_name, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(cards)

# Creates an Anki deck from a list of card data, and saves it to an .apkg file.
def create_anki_deck(deck_name, cards, output_file):
    print('Creating Anki deck.')

    # Define the Anki model
    model = genanki.Model(
        model_id=anki_model_id,
        name='English Vocab Model',
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
    print('Adding notes to the Anki deck.')
    media_files = []
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[card['Front'], card['Back'], card.get('AudioTag', '')])
        deck.add_note(note)
        media_files.append(f"{card['AudioPath']}")

    # Save the deck to a file with attached media files
    genanki.Package(deck, media_files=media_files).write_to_file(output_file)
    print(f"Anki deck saved as {output_file}")

# Translates a list of sentences and creates a list of cards with translations and audio tags
def generate_translated_cards(sentences):
    print('Initializing translation.')
    with Pool(cpu_count()) as pool:
        cards = pool.map(partial(create_translated_card), sentences)
    return cards

# Translates a sentence, generates an audio tag, and creates a card with the translation and audio
def create_translated_card(sentence):
    print('Translating sentence: ' + sentence)
    translator = Translator()
    translation = translator.translate(sentence, src='en', dest='pt')
    current_card = {"Front": sentence, "Back": translation.text}

    audio_file_name, audio_file_path  = generate_audio(sentence) 
    current_card["AudioTag"] = f"[sound:{audio_file_name}.mp3]"
    current_card["AudioPath"] = audio_file_path

    return current_card

# Generates an audio for a given text using Azure Speech API and saves the audio file as an MP3
def generate_audio(text, audio_output_dir=AUDIO_OUTPUT_DIR):
    audio_file_name = slugify(text)
    audio_file_path = f"{audio_output_dir}/{audio_file_name}.mp3"
    print(f"Checking if audio file {audio_file_path} exists.")
    if not os.path.exists(audio_file_path):
        print(f"File {audio_file_path} do not exists, creating file using Azure Speech API.")
        audio_config = AudioConfig(filename=audio_file_path)
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        synthesizer.speak_text(text)
    return [audio_file_name, audio_file_path]

# Reads an input file, generates translated cards with audio,
# and creates either an Anki deck or a CSV file based on the specified output format.
def anki_deck_creator(input_file_name, output_file_name, output_format):
    # Create necessary directories
    os.makedirs(f"{OUTPUT_DIR}", exist_ok=True)
    os.makedirs(f"{AUDIO_OUTPUT_DIR}", exist_ok=True)

    # Read input file
    sentences = read_input_file(f'{INPUT_DIR}/' + input_file_name)

    # Generate translated cards
    cards = generate_translated_cards(sentences)

    # Write output file
    if output_format == 'anki':
        create_anki_deck(output_file_name, cards, f"{OUTPUT_DIR}/{output_file_name}.apkg")
    elif output_format == 'csv':
        write_csv_file(f'{OUTPUT_DIR}/{output_file_name}.csv', cards)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Create Anki decks or CSV files from a CSV input file.')
    parser.add_argument('--input', help='The input CSV file name')
    parser.add_argument('--format', choices=['anki', 'csv'], default='anki', help='The output format (default: anki)')
    parser.add_argument('--output', help='The output file name')
    args = parser.parse_args()

    input_file_name = args.input
    output_file_name = os.path.splitext(args.output if args.output else input_file_name)[0]
    output_format = args.format
    start_time = time.time()
    anki_deck_creator(input_file_name, output_file_name, output_format)
    num_cards = len(read_input_file(f'{INPUT_DIR}/' + input_file_name))
    end_time = time.time()
    time_taken = end_time - start_time
    print(f"Generated {num_cards} cards in {time_taken:.2f} seconds.")
