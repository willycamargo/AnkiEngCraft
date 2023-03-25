import sys
import csv
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
    if len(sys.argv) < 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)

    file_name = sys.argv[1]
    csv_data = read_csv('input/' + file_name)
    sentences = [d['Sentence'] for d in csv_data]
    cards = create_cards_with_translation(sentences)
    write_csv('output/' + file_name, cards)