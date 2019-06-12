import pickle

with open('points.dat', 'rb') as f:
    imageData = pickle.load(f)

    for i in imageData:
        print(i)
