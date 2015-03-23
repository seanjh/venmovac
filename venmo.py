import pymongo
import nltk
import datetime


CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']


def parse_words():
    venmoWordContainer = {}
    collection = DB['trans']
    collection_size = 1000000
    print 'Processing:\t', collection_size, ' documents'
    print "*"*50

    # count the words
    count = 1
    for doc in collection.find()[:1000000]:
        text = nltk.tokenize.word_tokenize(doc['message'])
        tokenized = nltk.pos_tag(text)
        nouns = [s[0] for s in tokenized if s[1] == 'NN']
        for n in nouns:
            if n not in venmoWordContainer:
                venmoWordContainer[n] = 1
            else:
                venmoWordContainer[n] += 1

        # Progress tracker
        count += 1
        if ((1.0 * count) / collection_size) * 100 % 1 == 0:
            print str(((1.0 * count) / collection_size) * 100) + "%"

    # write to a file
    write_to_file(venmoWordContainer)


def write_to_file(d):
    with open("venmoWords.csv", "w") as r:
        for k, v in d.items():
            r.write(normalizeText(k) + "," + str(v) + "\n")


def normalizeText(s):
    if type(s) == unicode:
        return s.encode('utf8', 'ignore')
    else:
        return str(s)


if __name__ == '__main__':
    tic = datetime.datetime.now()
    parse_words()
    toc = datetime.datetime.now()
    print toc - tic
