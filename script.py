import sys
import os
import csv
import argparse
import genanki
from dotenv import load_dotenv
from functools import partial
from googletrans import Translator
from multiprocessing import Pool, cpu_count
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig

load_dotenv()

speech_key = os.getenv('AZURE_SPEECH_KEY')
service_region = os.getenv('AZURE_REGION')

def read_csv(file_name):
    print('Reading initial CSV file...')
    with open(file_name, 'r') as f:
        reader = csv.DictReader(f)
        csv_data = list(reader)
        return csv_data


def write_csv(file_name, cards):
    print('Writing final CSV file...')
    keys = cards[0].keys()
    with open(file_name, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(cards)

def create_anki_deck(deck_name, cards):
    print('Creating Anki deck...')

    # Define the Anki model
    model = genanki.Model(
        model_id=1607392319,
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
        deck_id=2059400110,
        name=deck_name)

    # Add notes (cards) to the deck
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[card['Front'], card['Back'], card.get('Audio', '')])
        deck.add_note(note)

    # Add notes (cards) to the deck and collect audio file paths
    media_files = []
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[card['Front'], card['Back'], card.get('Audio', '')])
        deck.add_note(note)

        if 'Audio' in card:
            media_files.append(f"output/audio/{card['Front']}.mp3")

    # Save the deck to a file with attached media files
    genanki.Package(deck, media_files=media_files).write_to_file(f"output/{deck_name}.apkg")  # Update this line
    print(f"Anki deck saved as output/{deck_name}.apkg")

def translate_sentence(sentence):
    print('Translating sentence: ' + sentence)
    translator = Translator()
    translation = translator.translate(sentence, src='en', dest='pt')
    current_card = {"Front": sentence, "Back": translation.text}

    speech_config = SpeechConfig(subscription=speech_key, region=service_region)
    audio_tag = synthesize_speech(sentence, speech_config)
    current_card["Audio"] = audio_tag

    return current_card


def synthesize_speech(text, speech_config):
    audio_config = AudioConfig(filename=f"output/audio/{text}.mp3")
    synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    synthesizer.speak_text(text)
    return f"[sound:{text}.mp3]"


def create_cards_with_translation(sentences):
    print('Initializing translation...')
    with Pool(cpu_count()) as pool:
        cards = pool.map(partial(translate_sentence), sentences)
    return cards

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)

    parser = argparse.ArgumentParser(description='Create Anki decks or CSV files from a CSV input file.')
    parser.add_argument('--filename', help='The input CSV file name')
    parser.add_argument('--output', choices=['anki', 'csv'], default='anki', help='The output format (default: anki)')
    args = parser.parse_args()

    file_name = args.filename
    csv_data = read_csv('input/' + file_name)
    sentences = [d['Sentence'] for d in csv_data]
    cards = create_cards_with_translation(sentences)
    if args.output == 'anki':
        create_anki_deck(file_name.replace('.csv', ''), cards)
    elif args.output == 'csv':
        write_csv('output/' + file_name, cards)

