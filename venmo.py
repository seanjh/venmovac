import pymongo
import nltk


CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']
venmoWordContainer = {}


def parse_words():
    global venmoWordContainer
    collection = DB['trans']

    print 'Processing:\t', collection.count(), ' documents'
    print "*"*50

    # count the words
    for doc in collection.find()[:100]:
        text = nltk.tokenize.word_tokenize(doc['message'])
        tokenized = nltk.pos_tag(text)
        nouns = [s[0] for s in tokenized if s[1] == 'NN']
        for n in nouns:
            if n not in venmoWordContainer:
                venmoWordContainer[n] = 1
            else:
                venmoWordContainer[n] += venmoWordContainer[n]

    # write to a file
    write_to_file(venmoWordContainer)


def write_to_file(d):
    with open("venmoWords.csv", "w") as r:
        for k, v in d.items():
            print k, "\t", v
            r.write(normalizeText(k) + "," + str(v) + "\n")


def normalizeText(s):
    if type(s) == unicode:
        return s.encode('utf8', 'ignore')
    else:
        return str(s)


if __name__ == '__main__':
    parse_words()
