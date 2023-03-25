import sys
import csv
import argparse
import genanki
from googletrans import Translator
from multiprocessing import Pool, cpu_count


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
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
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
            fields=[card['Front'], card['Back']])
        deck.add_note(note)

    # Save the deck to a file
    genanki.Package(deck).write_to_file(f"output/{deck_name}.apkg")
    print(f"Anki deck saved as output/{deck_name}.apkg")

def translate_sentence(sentence):
    translator = Translator()
    print('Translating sentence: ' + sentence)
    translation = translator.translate(sentence, src='en', dest='pt')
    current_card = {
        "Front": sentence,
        "Back": translation.text
    }
    return current_card


def create_cards_with_translation(sentences):
    print('Initializing translation...')
    with Pool(cpu_count()) as pool:
        cards = pool.map(translate_sentence, sentences)
    return cards


if __name__ == "__main__":
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

