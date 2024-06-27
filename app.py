import os
import re
import time
import random
from flask import Flask, render_template, request, jsonify
from pythainlp.tokenize import word_tokenize, syllable_tokenize
from pythainlp.transliterate import pronunciate
from pythainlp.khavee import KhaveeVerifier
from pythainlp.soundex.sound import word_approximation
from pythainlp.util import rhyme, Trie
from pythainlp.corpus import thai_words

app = Flask(__name__)
kv = KhaveeVerifier()

# Load Thai words into a trie for fast autocomplete
words = list(thai_words())
trie = Trie(words)

def remove_sara(word):
    thai_vowels = 'ะาำิีึืุูเแโใไัา็่้๊๋์'
    if word and word[0] in thai_vowels:
        return word[1:]
    return word

def first_phayanchana(word):
    thai_consonants = 'กขฃคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ'
    for char in word:
        if char in thai_consonants:
            return char
    return ''

def check_phayanchana(text):
    leading_cases = {
        'หน': 'น',
        'หม': 'ม',
        'หย': 'ย',
        'หร': 'ร',
        'หล': 'ล',
        'หว': 'ว',
        'หง': 'ง',
        'หญ': 'ย',
        'อย': 'ย',
    }

    words = text.split()
    modified_words = []
    initial_consonants = []
    for word in words:
        word = remove_sara(word)
        modified_word = word
        for leading, replacement in leading_cases.items():
            if word.startswith(leading):
                modified_word = word.replace(leading, replacement, 1)
                break
        modified_words.append(modified_word)
        initial_consonants.append(first_phayanchana(modified_word))
    remove_nam = ' '.join(modified_words)
    f_phayanchana = ' '.join(initial_consonants)
    return f_phayanchana, remove_nam

def check_and_recommend(first_word):
    list_sumpus = rhyme(first_word)
    filtered_words = []
    unwanted_endings = 'ฑษฒญณฐธฎฤฆฏฌศซฉฮฬฝ'
    for word in list_sumpus:
        pronunciation = pronunciate(word, engine="w2p")
        if pronunciation.count('-') <= 2 and word[-1] not in unwanted_endings:
            if not re.search(r'[ๆ\\\/ฯ\s ]', word):
                filtered_words.append(word)
    approximation_scores = word_approximation(first_word, filtered_words)
    filtered_words = [filtered_words[i] for i, score in enumerate(approximation_scores) if
                      score > 0.0 and score <= 12.0]
    if len(filtered_words) > 5:
        filtered_words = random.sample(filtered_words, 5)
    return filtered_words

def check_sumpus(word1, word2):
    return kv.check_sara(check_phayanchana(word1)[1]) == kv.check_sara(check_phayanchana(word2)[1]) or \
        check_phayanchana(word1)[0] == check_phayanchana(word2)[0]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('query', '')
    if query:
        tokens = word_tokenize(query)
        last_token = tokens[-1]
        suggestions = [word for word in trie if word.startswith(last_token)][:5]
        suggestions = [query + suggestion[len(last_token):] for suggestion in suggestions]
    else:
        suggestions = []
    return jsonify(suggestions)

@app.route('/check_rhyme', methods=['POST'])
def check_rhyme():
    start_time = time.time()
    text = request.form['text']

    conv0 = syllable_tokenize(text)
    print(f"conv0 = {conv0}")

    conv = word_tokenize(text, engine="newmm")
    while conv and conv[0].strip() == '':
        conv.pop(0)
    while conv and conv[-1].strip() == '':
        conv.pop(-1)
    print(f"คำที่แยกได้: {conv}")

    pronunciations = [pronunciate(word, engine="w2p") if word.strip() else ' ' for word in conv]
    print(f"การออกเสียง: {pronunciations}")

    cleaned_pronunciations = [word.replace('ฺ', '') for word in pronunciations]
    print(f"ลบพินทุ (◌ฺ): {cleaned_pronunciations}")

    syllables = []
    for word in cleaned_pronunciations:
        if word == ' ':
            syllables.append(' ')
        else:
            syllables.extend(word.split('-'))
    syllables.append(' ')
    print(f"พยางค์ที่แยกได้: {syllables}")

    spaces_indices = [i for i, x in enumerate(syllables) if x == ' ']
    lists = []
    start = 0
    for index in spaces_indices:
        lists.append(syllables[start:index])
        start = index + 1
    print(f"แยก lists: {lists}")

    word_count = len([word for word in syllables if word.strip()])
    print(f"จำนวนคำที่ไม่รวมช่องว่าง: {word_count}")

    messages = []
    lists_status = ['green'] * len(lists)
    display_words = []

    for group_start in range(0, len(lists), 8):
        for i in range(group_start, min(group_start + 8, len(lists))):
            if len(lists[i]) < 1:
                continue

            verse_index = (i - group_start) + 1
            next_verse_index = (i - group_start) + 2

            if i == group_start and len(lists) > i + 1 and len(lists[i + 1]) >= 3:
                last_word_i = lists[i][-1]
                third_word_next = lists[i + 1][2]
                fifth_word_next = lists[i + 1][4] if len(lists[i + 1]) >= 5 else None
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {third_word_next if third_word_next else fifth_word_next if fifth_word_next else lists[i + 1][-1]} วรรคที่ {next_verse_index}"
                if check_sumpus(last_word_i, third_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, third_word_next)))
                if not check_sumpus(last_word_i, third_word_next) and (fifth_word_next is None or not check_sumpus(last_word_i, fifth_word_next)):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ1 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{third_word_next}' หรือ '{fifth_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 1] = 'red'

            if i == group_start + 2 and len(lists) > i + 1 and len(lists[i + 1]) >= 3:
                last_word_i = lists[i][-1]
                third_word_next = lists[i + 1][2]
                fifth_word_next = lists[i + 1][4] if len(lists[i + 1]) >= 5 else None
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {third_word_next if third_word_next else fifth_word_next if fifth_word_next else lists[i + 1][-1]} วรรคที่ {next_verse_index}"
                if check_sumpus(last_word_i, third_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, third_word_next)))
                if not check_sumpus(last_word_i, third_word_next) and (fifth_word_next is None or not check_sumpus(last_word_i, fifth_word_next)):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ2 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{third_word_next}' หรือ '{fifth_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 1] = 'red'

            if i == group_start + 4 and len(lists) > i + 1 and len(lists[i + 1]) >= 3:
                last_word_i = lists[i][-1]
                third_word_next = lists[i + 1][2]
                fifth_word_next = lists[i + 1][4] if len(lists[i + 1]) >= 5 else None
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {third_word_next if third_word_next else fifth_word_next if fifth_word_next else lists[i + 1][-1]} วรรคที่ {next_verse_index}"
                if check_sumpus(last_word_i, third_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, third_word_next)))
                if not check_sumpus(last_word_i, third_word_next) and (fifth_word_next is None or not check_sumpus(last_word_i, fifth_word_next)):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ3 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{third_word_next}' หรือ '{fifth_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 1] = 'red'

            if i == group_start + 6 and len(lists) > i + 1 and len(lists[i + 1]) >= 3:
                last_word_i = lists[i][-1]
                third_word_next = lists[i + 1][2]
                fifth_word_next = lists[i + 1][4] if len(lists[i + 1]) >= 5 else None
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {third_word_next if third_word_next else fifth_word_next if fifth_word_next else lists[i + 1][-1]} วรรคที่ {next_verse_index}"
                if check_sumpus(last_word_i, third_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, third_word_next)))
                if not check_sumpus(last_word_i, third_word_next) and (fifth_word_next is None or not check_sumpus(last_word_i, fifth_word_next)):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ4 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{third_word_next}' หรือ '{fifth_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 1] = 'red'

            if i == group_start + 1 and len(lists) > i + 1 and len(lists[i + 1]) >= 8:  # Ensure list has at least 8 words for last word checks
                last_word_i = lists[i][-1]
                if len(lists) > i + 1 and len(lists[i + 1]) > 0:
                    last_word_next = lists[i + 1][-1]
                    word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {last_word_next} วรรคที่ {next_verse_index}"
                    if check_sumpus(last_word_i, last_word_next):
                        word_pair += " สัมผัสกัน"
                    else:
                        word_pair += " ไม่สัมผัสกัน"
                    display_words.append((word_pair, check_sumpus(last_word_i, last_word_next)))
                    if not check_sumpus(last_word_i, last_word_next):
                        recommendations = check_and_recommend(last_word_i)
                        messages.append(
                            f"บทที่ {int(group_start / 8) + 1} คำ5 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{last_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                        lists_status[i] = 'red'
                        lists_status[i + 1] = 'red'

            if i == group_start + 3 and len(lists) > i + 2 and len(lists[i + 2]) > 0 and len(lists[i + 1]) >= 8:  # Ensure list has at least 8 words for last word checks
                last_word_i = lists[i][-1]
                last_word_next = lists[i + 2][-1]
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {last_word_next} วรรคที่ {next_verse_index + 1}"
                if check_sumpus(last_word_i, last_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, last_word_next)))
                if not check_sumpus(last_word_i, last_word_next):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ6 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{last_word_next}' ของวรรค {next_verse_index + 1} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 2] = 'red'

            if i == group_start + 5 and len(lists) > i + 1 and len(lists[i + 1]) > 0 and len(lists[i + 1]) >= 8:  # Ensure list has at least 8 words for last word checks
                last_word_i = lists[i][-1]
                last_word_next = lists[i + 1][-1]
                word_pair = f"{last_word_i} วรรคที่ {verse_index} และ {last_word_next} วรรคที่ {next_verse_index}"
                if check_sumpus(last_word_i, last_word_next):
                    word_pair += " สัมผัสกัน"
                else:
                    word_pair += " ไม่สัมผัสกัน"
                display_words.append((word_pair, check_sumpus(last_word_i, last_word_next)))
                if not check_sumpus(last_word_i, last_word_next):
                    recommendations = check_and_recommend(last_word_i)
                    messages.append(
                        f"บทที่ {int(group_start / 8) + 1} คำ7 '{last_word_i}' ของวรรค {verse_index} ไม่สัมผัสกับ '{last_word_next}' ของวรรค {next_verse_index} และแนะนำคำที่สัมผัส คือ: {recommendations}")
                    lists_status[i] = 'red'
                    lists_status[i + 1] = 'red'

    end_time = time.time()
    elapsed_time = end_time - start_time
    print()
    return jsonify({
        'messages': messages,
        'lists_status': lists_status,
        'display_words': display_words,
        'processing_time': elapsed_time,
        'word_count': word_count
    })

if __name__ == '__main__':
    app.run(debug=True)
