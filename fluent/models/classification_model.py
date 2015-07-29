# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2015, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

import copy
import math
import numpy
import os
import pandas
import random

from collections import Counter

try:
  import simplejson as json
except ImportError:
  import json



class ClassificationModel(object):
  """
  Base class for NLP models of classification tasks. When inheriting from this
  class please take note of which methods MUST be overridden, as documented
  below. The Model superclass mainly implements evaluation methods.

  Methods/properties that must be implemented by subclasses:
    - encodePattern(); note the specified format in the docstring below.
    - resetModel()
    - trainModel()
    - testModel()

  TODO: confusion matrices
  TODO: use nupic.bindings.math import Random
  """

  def __init__(self, n=16384, w=328, verbosity=1, numLabels=3):
    """The SDR dimensions are standard for Cortical.io fingerprints."""
    self.n = n
    self.w = w
    self.numLabels = numLabels
    self.verbosity = verbosity


  def encodeRandomly(self, sample):
    """Return a random bitmap representation of the sample."""
    random.seed(sample)
    return numpy.sort(random.sample(xrange(self.n), self.w))


  def logEncodings(self, patterns, path):
    """Log the encoding dictionaries to a txt file."""
    if not os.path.isdir(path):
      raise ValueError("Invalid path to write file.")

    # Cast numpy arrays to list objects for serialization.
    jsonPatterns = copy.deepcopy(patterns)
    for jp in jsonPatterns:
      jp["pattern"]["bitmap"] = jp["pattern"].get("bitmap", None).tolist()
      jp["labels"] = jp.get("labels", None).tolist()

    with open(os.path.join(path, "encoding_log.txt"), "w") as f:
      f.write(json.dumps(jsonPatterns, indent=1))


  def classifyRandomly(self, labels):
    """Return accuracy of random classifications for the labels."""
    randomLabels = numpy.random.randint(0, labels.max(), labels.shape)
    return (randomLabels == labels).sum() / float(labels.shape[0])


  def _densifyPattern(self, bitmap):
    """Return a numpy array of 0s and 1s to represent the input bitmap."""
    densePattern = numpy.zeros(self.n)
    for i in bitmap:
      densePattern[i] = 1.0
    return densePattern


  def compare(self, bitmap1, bitmap2):
    """
    @param bitmap1     (list)               indices of on bits
    @param bitmap2     (list)               indices of on bits
    @return dist       (dict)               distance metric name to distance

    Compare bitmaps, returning the distances between the bitmaps
    Example return dict:
      {
        "cosineSimilarity": 0.6666666666666666,
        "euclideanDistance": 0.3333333333333333,
        "jaccardDistance": 0.5,
        "overlappingAll": 6,
        "overlappingLeftRight": 0.6666666666666666,
        "overlappingRightLeft": 0.6666666666666666,
        "sizeLeft": 9,
        "sizeRight": 9
      }
    """
    if len(bitmap1) == 0 or len(bitmap2) == 0:
      raise ValueError("Bitmaps must have on bits to compare")

    sdr1 = numpy.zeros(self.n)
    sdr2 = numpy.zeros(self.n)
    sdr1[bitmap1] = 1
    sdr2[bitmap2] = 1

    dist = {
      "sizeLeft": float(len(bitmap1)),
      "sizeRight": float(len(bitmap2)),
      "overlappingAll": float(len(numpy.intersect1d(bitmap1, bitmap2))),
      "euclideanDistance": numpy.linalg.norm(sdr1 - sdr2)
    }

    dist["overlappingLeftRight"] = dist["overlappingAll"] / dist["sizeLeft"]
    dist["overlappingRightLeft"] = dist["overlappingAll"] / dist["sizeRight"]
    dist["cosineSimilarity"] = dist["overlappingAll"] / \
      (math.sqrt(dist["sizeLeft"]) * math.sqrt(dist["sizeRight"]))
    dist["jaccardDistance"] = 1 - (dist["overlappingAll"] / \
      len(numpy.union1d(bitmap1, bitmap2)))

    return dist


  @staticmethod
  def getWinningLabels(labelFreq, numLabels=3):
    """
    Returns indices of input array, sorted for highest to lowest value. E.g.
      >>> labelFreq = array([ 0., 4., 0., 1.])
      >>> winners = getWinningLabels(labelFreq, numLabels=3)
      >>> print winners
      array([1, 3])
    Note:
      - indices of nonzero values are not included in the returned array
      - ties are handled randomly

    @param labelFreq    (numpy.array)   Ints that (in this context) represent
                                        the frequency of inferred labels.
    @param numLabels    (int)           Return this number of most frequent
                                        labels within top k
    @return             (numpy.array)   Indicates largest elements in labelFreq,
                                        sorted greatest to least. Length is up
                                        to numLabels.
    """
    # The use of numpy.lexsort() here is to first sort by labelFreq, then sort
    # by random values; this breaks ties in a random manner.
    if labelFreq is None:
      return numpy.array([])

    randomValues = numpy.random.random(labelFreq.size)
    winners = numpy.lexsort((randomValues, labelFreq))[::-1][:numLabels]

    return numpy.array([i for i in winners if labelFreq[i] > 0])


  def calculateClassificationResults(self, classifications):
    """
    Calculate the classification accuracy for each category.

    @param classifications  (list)          Two lists: (0) predictions and (1)
        actual classifications. Items in the predictions list are lists of
        ints or None, and items in actual classifications list are ints.

    @return                 (list)          Tuples of class index and accuracy.
    """
    if len(classifications[0]) != len(classifications[1]):
      raise ValueError("Classification lists must have same length.")

    if len(classifications[1]) == 0:
      return []

    # Get all possible labels
    labels = list(set([l for actual in classifications[1] for l in actual]))

    labels_to_idx = {l: i for i,l in enumerate(labels)}
    correctClassifications = numpy.zeros(len(labels))
    totalClassifications = numpy.zeros(len(labels))
    for actual, predicted in zip(classifications[1], classifications[0]):
      for a in actual:
        idx = labels_to_idx[a]
        totalClassifications[idx] += 1
        if a in predicted:
          correctClassifications[idx] += 1

    return zip(labels, correctClassifications / totalClassifications)


  def evaluateResults(self, classifications, references, idx):
    """
    Calculate statistics for the predicted classifications against the actual.

    @param classifications  (tuple)     Two lists: (0) predictions and
        (1) actual classifications. Items in the predictions list are numpy
        arrays of ints or [None], and items in actual classifications list
        are numpy arrays of ints.

    @param references       (list)            Classification label strings.

    @param idx              (list)            Indices of test samples.

    @return                 (tuple)           Returns a 2-item tuple w/ the
        accuracy (float) and confusion matrix (numpy array).
    """
    if self.verbosity > 0:
      self.printTrialReport(classifications, references, idx)

    accuracy = self.calculateAccuracy(classifications)
    cm = self.calculateConfusionMatrix(classifications, references)

    return (accuracy, cm)


  def evaluateCumulativeResults(self, intermResults):
    """
    Cumulative statistics for the outputs of evaluateTrialResults().

    @param intermResults      (list)          List of returned results from
                                              evaluateTrialResults().
    @return                   (dict)          Returns a dictionary with entries
                                              for max, mean, and min accuracies,
                                              and the mean confusion matrix.
    """
    accuracy = []
    cm = numpy.zeros((intermResults[0][1].shape))

    # Find mean, max, and min values for the metrics.
    for result in intermResults:
      accuracy.append(result[0])
      cm = numpy.add(cm, result[1])

    results = {"max_accuracy":max(accuracy),
               "mean_accuracy":sum(accuracy)/float(len(accuracy)),
               "min_accuracy":min(accuracy),
               "total_cm":cm}

    if self.verbosity > 0:
      self.printCumulativeReport(results)

    return results


  @staticmethod
  def calculateAccuracy(classifications):
    """
    @param classifications    (tuple)     First element is list of predicted
        labels, second is list of actuals; items are numpy arrays.

    @return                   (float)     Correct labels out of total labels,
        where a label is correct if it is amongst the actuals.
    """
    if len(classifications[0]) != len(classifications[1]):
      raise ValueError("Classification lists must have same length.")

    if len(classifications[1]) == 0:
      return None

    accuracy = 0.0
    for actual, predicted in zip(classifications[1], classifications[0]):
      commonElems = numpy.intersect1d(actual, predicted)
      accuracy += len(commonElems)/float(len(actual))

    return accuracy/len(classifications[1])


  @staticmethod
  def calculateConfusionMatrix(classifications, references):
    """
    Returns confusion matrix as a pandas dataframe.

    TODO: Figure out better way to report multilabel outputs--only handles
    single label now. So for now return empty array.
    """
    return numpy.array([])

    if len(classifications[0]) != len(classifications[1]):
      raise ValueError("Classification lists must have same length.")

    total = len(references)
    cm = numpy.zeros((total, total+1))
    for actual, predicted in zip(classifications[1], classifications[0]):
      if predicted is not None:
        cm[actual[0]][predicted[0]] += 1
      else:
        # No predicted label, so increment the "(none)" column.
        cm[actual[0]][total] += 1
    cm = numpy.vstack((cm, numpy.sum(cm, axis=0)))
    cm = numpy.hstack((cm, numpy.sum(cm, axis=1).reshape(total+1,1)))

    cm = pandas.DataFrame(
      data=cm,
      columns=references+["(none)"]+["Actual Totals"],
      index=references+["Prediction Totals"])

    return cm


  @staticmethod
  def printTrialReport(labels, refs, idx):
    """
    Print columns for sample #, actual label, and predicted label.

    TODO: move to Runner
    """
    template = "{0:<10}|{1:<55}|{2:<55}"
    print "Evaluation results for the trial:"
    print template.format("#", "Actual", "Predicted")
    for i in xrange(len(labels[0])):
      if not any(labels[0][i]):
        # No predicted classes for this sample.
        print template.format(idx[i],
                              [refs[label] for label in labels[1][i]],
                              "(none)")
      else:
        print template.format(idx[i],
                              [refs[label] for label in labels[1][i]],
                              [refs[label] for label in labels[0][i]])


  @staticmethod
  def printCumulativeReport(results):
    """
    Prints results as returned by evaluateFinalResults() after several trials.

    TODO: pprint, move to Runner
    """
    print "---------- RESULTS ----------"
    print "max, mean, min accuracies = "
    print "{0:.3f}, {1:.3f}, {2:.3f}".format(
    results["max_accuracy"], results["mean_accuracy"], results["min_accuracy"])
    print "total confusion matrix =\n", results["total_cm"]


  @staticmethod
  def printFinalReport(trainSize, accuracies):
    """
    Prints result accuracies.

    TODO: move to Runner
    """
    template = "{0:<20}|{1:<10}"
    print "Evaluation results for this experiment:"
    print template.format("Size of training set", "Accuracy")
    for i, a in enumerate(accuracies):
      print template.format(trainSize[i], a)


  def encodePattern(self, pattern):
    """
    The subclass implementations must return the encoding in the following
    format:
      {
        ["text"]:sample,
        ["sparsity"]:sparsity,
        ["bitmap"]:bitmapSDR
      }
    Note: sample is a string, sparsity is float, and bitmapSDR is a numpy array.
    """
    raise NotImplementedError


  def resetModel(self):
    raise NotImplementedError


  def trainModel(self, samples, labels):
    raise NotImplementedError


  def testModel(self, sample, numLabels):
    raise NotImplementedError
