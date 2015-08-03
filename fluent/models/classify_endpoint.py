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

import numpy
import os

from collections import defaultdict
from cortipy.cortical_client import CorticalClient
from cortipy.exceptions import UnsuccessfulEncodingError
from fluent.encoders.cio_encoder import CioEncoder
from fluent.models.classification_model import ClassificationModel



class ClassificationModelEndpoint(ClassificationModel):
  """
  Class to run the survey response classification task with Cortical.io
  text endpoint encodings and classification system.

  From the experiment runner, the methods expect to be fed one sample at a time.
  """

  def __init__(self, verbosity=1, numLabels=3):
    """
    Initialize the CorticalClient and CioEncoder. Requires a valid API key
    """
    super(ClassificationModelEndpoint, self).__init__(verbosity, numLabels)

    self.encoder = CioEncoder(cacheDir="./experiments/cache")
    self.client = CorticalClient(self.encoder.apiKey)

    self.n = self.encoder.n
    self.w = int((self.encoder.targetSparsity/100) * self.n)

    self.categoryBitmaps = {}
    self.negatives = defaultdict(list)
    self.positives = defaultdict(list)


  def encodePattern(self, sample):
    """
    Encode an SDR of the input string by querying the Cortical.io API.

    @param sample         (list)          Tokenized sample, where each item is
                                          a string
    @return fp            (dict)          The sample text, sparsity, and bitmap.
    Example return dict:
      {
        "text": "Example text",
        "sparsity": 0.03,
        "bitmap": numpy.array([])
      }
    """
    sample = " ".join(sample)
    fpInfo = self.encoder.encode(sample)
    if fpInfo:
      fp = {"text":fpInfo["text"] if "text" in fpInfo else fpInfo["term"],
            "sparsity":fpInfo["sparsity"],
            "bitmap":numpy.array(fpInfo["fingerprint"]["positions"])
            }
    else:
      fp = {"text":sample,
            "sparsity":float(self.w)/self.n,
            "bitmap":self.encodeRandomly(sample)
            }

    return fp


  def resetModel(self):
    """Reset the model"""
    self.positives.clear()
    self.negatives.clear()
    self.categoryBitmaps.clear()


  def trainModel(self, samples, labels, negatives=None):
    """
    Train the classifier on the input sample and label. Use Cortical.io's
    createClassification to make a bitmap that represents the class

    @param samples    (list)            List of dictionaries containing the
                                        sample text, sparsity, and bitmap.
    @param labels     (list)            List of numpy arrays containing the
                                        reference indices for the
                                        classifications of each sample.
    @param negatives  (list)            Each item is the dictionary containing
                                        text, sparsity and bitmap for the
                                        negative samples.

    TODO: move Cortical.io client logic to CioEncoder.
    """
    labelsToUpdateBitmaps = set()
    for sample, sampleLabels in zip(samples, labels):
      for label in sampleLabels:
        try:
          fpInfo = self.client.getTextBitmap(sample["text"])
        except UnsuccessfulEncodingError:
          fpInfo = None

        if sample["text"] and fpInfo:
          self.positives[label].append(sample["text"])

          # Only add negatives when training on one sample so we know which
          # labels to use
          if negatives and len(samples) == 1:
            for neg in negatives:
              if neg["text"]:
                self.negatives[label].append(neg["text"])
          labelsToUpdateBitmaps.add(label)

    for label in labelsToUpdateBitmaps:
      try:
        self.categoryBitmaps[label] = self.client.createClassification(
            str(label),
            self.positives[label],
            self.negatives[label])["positions"]
      except UnsuccessfulEncodingError:
        self._unsuccessfulEncodingFallback(label)


  def _unsuccessfulEncodingFallback(self, label):
    """
    When cortipy cannot create the classification because one of the texts
    can't be encoded, this finds the sample that has issues
    """
    print "Uncucessful encoding for {}. Using fallback".format(label)
    possiblePositives = range(len(self.positives[label]))
    goodPositives = []
    # TODO: replace with binary search to speed up finding the bad ones
    positivesArray = numpy.array(self.positives[label])
    for i in possiblePositives:
      try:
        self.categoryBitmaps[label] = self.client.createClassification(
            str(label),
            (positivesArray[goodPositives + [i]]).tolist(),
            self.negatives[label])["positions"]
        goodPositives += [i]
      except:
        print self.positives[label][i]
    self.positives[label] = (positivesArray[goodPositives]).tolist()


  def testModel(self, sample, numLabels=3, metric="overlappingAll"):
    """
    Test the Cortical.io classifier on the input sample. Returns a dictionary
    containing various distance metrics between the sample and the classes.

    @param sample         (dict)      The sample text, sparsity, and bitmap.
    @return               (list)      Winning classifications based on the
                                      specified metric. The number of items
                                      returned will be <= numLabels.
    """
    sampleBitmap = sample["bitmap"].tolist()

    distances = defaultdict(list)
    for cat, catBitmap in self.categoryBitmaps.iteritems():
      distances[cat] = self.compare(sampleBitmap, catBitmap)

    return self.getWinningLabels(distances, numLabels=numLabels, metric=metric)


  @staticmethod
  def getWinningLabels(distances, numLabels, metric):
    """
    Return indices of winning categories, based off of the input metric.
    Overrides the base class implementation.
    """
    metricValues = numpy.array([v[metric] for v in distances.values()])
    sortedIdx = numpy.argsort(metricValues)

    # euclideanDistance and jaccardDistance are ascending
    descendingOrder = set(["overlappingAll", "overlappingLeftRight",
      "overlappingRightLeft", "cosineSimilarity", "weightedScoring"])
    if metric in descendingOrder:
      sortedIdx = sortedIdx[::-1]

    return numpy.array(
        [distances.keys()[catIdx] for catIdx in sortedIdx[:numLabels]])
