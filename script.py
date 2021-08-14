from googletrans import Translator
import csv


# translated = translator.translate('hello', src='en', dest='pt')
# print(translated)

def read_csv(fileName):
  print('Reading initial CSV file...')
  with open(fileName, 'r') as f:
    reader = csv.DictReader(f)
    csvData = list(reader)
    return csvData

def write_csv(fileName, cards):
  print('Writing final CSV file...')
  keys = cards[0].keys()
  with open(fileName, 'w', newline='')  as output_file:
      dict_writer = csv.DictWriter(output_file, keys)
      dict_writer.writeheader()
      dict_writer.writerows(cards)

def create_cards_with_translation(sentences):
  print('Initializing translation..')
  cards = []
  translator = Translator()
  
  for sentence in sentences:
    print('Translating sentence: ' + sentence)
    translation = translator.translate(sentence, src='en', dest='pt')
    currentCard = {
      "Front": sentence,
      "Back": translation.text
    }
    cards.append(currentCard)
  return cards

# Execution
fileName = 'Anki Cards - English Vocab 05.csv'
csvData = read_csv('input/' + fileName)
sentences = [d['sentence'] for d in csvData]
cards = create_cards_with_translation(sentences)
write_csv('output/' + fileName, cards)
