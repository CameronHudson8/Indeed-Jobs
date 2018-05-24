# Cameron Hudson
# 2018-05-23

import csv
import pickle
from sklearn.decomposition import PCA

import matplotlib.pyplot as plt
import numpy as np
import pylab as pl
from matplotlib import cm
from numpy import zeros
from sklearn import manifold
from sklearn.cluster import DBSCAN

# SELECTION OF CLUSTERING BASIS
CLUSTERPARAM = "summaryWords"

# Load data.
allWords = pickle.load(open("allWords.p", "rb"))
jobListings = pickle.load(open("jobListings.p", "rb"))
courseListings = pickle.load(open("courseListings.p", "rb"))
allListings = jobListings + courseListings

"""Return a dictionary with the same keys, but with normalized values.

dictWithNumericalValues The dictionary whose keys are to be normalized.
return The input dictionary, but with normalized keys.
"""


def normalize(dictWithNumericalValues):
    total = sum(dictWithNumericalValues.values())
    for key in dictWithNumericalValues:
        dictWithNumericalValues[key] /= total
    return dictWithNumericalValues


# Normalize by dividing by the total.
allWords = normalize(allWords)
for job in jobListings:
    job[CLUSTERPARAM] = normalize(job[CLUSTERPARAM])
for course in courseListings:
    course[CLUSTERPARAM] = normalize(course[CLUSTERPARAM])

# Calculate the relative significance of each word by dividing by the overall occurence.
for job in jobListings:
    for word in job[CLUSTERPARAM]:
        job[CLUSTERPARAM][word] /= allWords[word]
for course in courseListings:
    for word in course[CLUSTERPARAM]:
        course[CLUSTERPARAM][word] /= allWords[word]

# Convert data from dictionaries to a matrix.
allWordsList = []
X = []
listingTitles = [listing["title"] for listing in allListings]
for word in allWords:
    allWordsList.append(word)

for listing in allListings:
    listingWordsTemp = []
    for word in allWords:
        if not word in listing[CLUSTERPARAM]:
            listingWordsTemp.append(0)
        else:
            listingWordsTemp.append(listing[CLUSTERPARAM][word])
    X.append(listingWordsTemp)

# Check array / matrix sizes:
print("Number of listings = " + str(len(listingTitles)))
print("Number of words = " + str(len(allWordsList)))
print("Matrix dimensions = " + str(len(X)) + " x " + str(len(X[0])))

# Load the previously saved epsilon, if possible.
try:
    dbscanParams = pickle.load(open("dbscanParams.p", "rb"))
    epsilon = dbscanParams["epsilon"][CLUSTERPARAM]
    outlierFrac = dbscanParams["outlierFrac"][CLUSTERPARAM]
except:
    dbscanParams = {"epsilon": {}, "outlierFrac": {}}
    epsilon = {
        "summaryWords": 6785.53966920973,
        "titleWords": 20113.680024276135
    }[CLUSTERPARAM]
    outlierFrac = {
        "summaryWords": 0.059870550161812294,
        "titleWords": 0.05934959349593496
    }[CLUSTERPARAM]

"""Run DBSCAN.

return the resulting DBSCAN object.
"""


def runDbscan(epsilon):
    print("Running DBSCAN with epsilon of " + str(epsilon) + " ...")
    db = DBSCAN(eps=epsilon).fit(X)
    outlierFrac = getOutlierFrac(db)
    print("Outlier Fraction was " + str(outlierFrac) + ".")
    numClusters = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    print("Number of clusters = " + str(numClusters))
    dbscanParams["epsilon"][CLUSTERPARAM] = epsilon
    dbscanParams["outlierFrac"][CLUSTERPARAM] = outlierFrac
    pickle.dump(dbscanParams, open("dbscanParams.p", "wb"))
    return db


"""Based on the number of data points labeled as outliers, return the fraction that are outliers.

dbObj: The output of a DBSCAN call.
return: The fraction of points that are outliers.
"""


def getOutlierFrac(dbObj):
    labels = dbObj.labels_
    labelCounts = {}
    for label in labels:
        if label not in labelCounts:
            labelCounts[label] = 1
        else:
            labelCounts[label] += 1
    oF = labelCounts.get(-1, 0) / sum(labelCounts.values())
    print("Outlier Frac = " + str(oF))
    return oF


db = runDbscan(epsilon)
outlierFrac = getOutlierFrac(db)
labels = db.labels_

# Iterate DBSCAN to figure out a good epsilon
while (outlierFrac < 0.04 or outlierFrac > 0.06):

    print("epsilon in while loop = " + str(epsilon))
    # If there are too few outliers, decrease epsilon.
    if (outlierFrac < 0.04):
        factor = 0.95 / (1 - outlierFrac)
        print("outlierFrac in while loop = " + str(outlierFrac))
        epsilon *= factor

    # Otherwise, increase epsilon.
    else:
        epsilon /= (1 - outlierFrac) / 0.95

    print("new epsilon = " + str(epsilon))
    db = runDbscan(epsilon)
    outlierFrac = getOutlierFrac(db)
    labels = db.labels_


# Compute 2d projection.
unique_labels = set(labels)
colors = [cm.get_cmap("nipy_spectral")(each)
          for each in np.linspace(0, 1, len(unique_labels))]
colorArray = [colors[label + 1] for label in labels]

print("Computing manifold...")
mds = manifold.MDS(n_components=2, dissimilarity="euclidean")
results = mds.fit(X)
coords = results.embedding_
print("Manifold computed!")

# print("Computing principal components...")
# pca = PCA(n_components = 2)
# results = pca.fit(X)
# coords = pca.transform(X)
# print("Principal components computed!")


print("Creating plot...")
plt.subplots_adjust(bottom=0.1)

# For hover effect
fig, ax = plt.subplots()

norm = plt.Normalize(1, 4)
cmap = plt.cm.get_cmap("nipy_spectral")

sc = plt.scatter(coords[:, 0], coords[:, 1], marker='o', c=colorArray)

annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="w"),
                    arrowprops=dict(arrowstyle="->"))
annot.set_visible(False)

""" Update annotation on hover.

ind The index of the data point in X.
"""


def update_annot(ind):

    pos = sc.get_offsets()[ind["ind"][0]]
    annot.xy = pos
    text = "{}".format("\n".join([listingTitles[n] for n in ind["ind"]]))
    annot.set_text(text)
    annot.get_bbox_patch().set_facecolor(cmap(norm(labels[ind["ind"][0]])))
    annot.get_bbox_patch().set_alpha(0.4)


"""The callback for when the user mouses over a data point on the plot.

event An object containing the index of the data point over which the user is hovering.
"""


def hover(event):
    vis = annot.get_visible()
    if event.inaxes == ax:
        cont, ind = sc.contains(event)
        if cont:
            update_annot(ind)
            annot.set_visible(True)
            fig.canvas.draw_idle()
        else:
            if vis:
                annot.set_visible(False)
                fig.canvas.draw_idle()


fig.canvas.mpl_connect("motion_notify_event", hover)

print("Showing plot...")
plt.show()

# Find the most central data points in each cluster.
# First, refresh the data.
allWords = pickle.load(open("allWords.p", "rb"))
jobListings = pickle.load(open("jobListings.p", "rb"))
courseListings = pickle.load(open("courseListings.p", "rb"))
for job in jobListings:
    job["type"] = "job"
for course in courseListings:
    course["type"] = "course"
allListings = jobListings + courseListings

# For each cluster, find the listings most central to the cluster.
for unique_label in unique_labels:

    clusterListings = [allListings[i] for i in range(
        0, len(allListings)) if labels[i] == unique_label]

    # Repurpose allWords to specifically apply to this cluster.
    allWords = {}
    for listing in clusterListings:
        for word in listing[CLUSTERPARAM]:
            if word not in allWords:
                allWords[word] = 1
            else:
                allWords[word] += listing[CLUSTERPARAM][word]

    # Normalize by dividing by the total.
    allWords = normalize(allWords)
    for listing in clusterListings:
        listing[CLUSTERPARAM] = normalize(listing[CLUSTERPARAM])

    # Calculate the closeness of each listing to the average.
    for listing in clusterListings:
        listing["closeness"] = 0
        for word in listing[CLUSTERPARAM]:
            listing["closeness"] += (listing[CLUSTERPARAM]
                                     [word] - allWords[word]) ** 2
        listing["closeness"] = listing["closeness"] ** 0.5

    # Sort the listings by closeness to the average.
    clusterListings = sorted(clusterListings, key=lambda k: k["closeness"])

    # Save as CSV.
    with open("clusterParam " + CLUSTERPARAM + ", cluster " + str(unique_label) + ".csv", "w") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Rank", "Closeness", "Title"])
        i = 1
        for listing in clusterListings:
            if listing["type"] == "course":
                csvwriter.writerow(
                    [str(i), str(listing["closeness"]), listing["title"]])
                i += 1

print("Done.")
