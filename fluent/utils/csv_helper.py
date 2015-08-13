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
"""
This file contains CSV utility functions to use with nupic.fluent experiments.
"""

import csv
import os

from collections import defaultdict, OrderedDict


def readCSV(csvFile, sampleIdx, numLabels):
  """
  Read in a CSV file w/ the following formatting:
    - one header row
    - one page
    - one column of samples, followed by column(s) of labels

  @param csvFile         (str)          File name for the input CSV.
  @param sampleIdx       (int)          Column number of the text samples.
  @param numLabels       (int)          Number of columns of category labels.
  @return                (OrderedDict)  Keys are samples, values are lists of
                                        corresponding category labels (strings).
  """
  try:
    with open(csvFile) as f:
      reader = csv.reader(f)
      next(reader, None)
      
      dataDict = OrderedDict()
      labelIdx = range(sampleIdx + 1, sampleIdx + 1 + numLabels)

      for line in reader:
        dataDict[line[0]] = (line[sampleIdx],
                             [line[i] for i in labelIdx if line[i]])
    
      return dataDict

  except IOError as e:
    print e


def readDir(dirPath, sampleIdx, numLabels, modify=False):
  """
  Reads in data from a directory of CSV files; assumes the directory only
  contains CSV files.
  
  @param dirPath            (str)          Path to the directory.
  @param sampleIdx          (int)          Column number of the text samples.
  @param numLabels          (int)          Number of columns of category labels.
  @param modify             (bool)         Map the unix friendly category names
                                           to the actual names. 0 -> /, _ -> " "
  
  @return samplesDict       (defaultdict)  Keys are CSV names, values are
      OrderedDicts, where the keys/values are as specified in readCSV().
  """
  samplesDict = defaultdict(list)
  for _, _, files in os.walk(dirPath):
    for f in files:
      basename, extension = os.path.splitext(os.path.basename(f))
      if "." in basename and extension == ".csv":
        category = basename.split(".")[-1]
        if modify:
          category = category.replace("0", "/")
          category = category.replace("_", " ")
        samplesDict[category] = readCSV(os.path.join(dirPath, f), sampleIdx, numLabels)

  return samplesDict


def writeCSV(data, headers, csvFile):
  """Write data with column headers to a CSV."""
  with open(csvFile, "wb") as f:
    writer = csv.writer(f, delimiter=",")
    writer.writerow(headers)
    writer.writerows(data)


def writeFromDict(dataDict, headers, csvFile):
  """
  Write dictionary to a CSV, where keys are row numbers and values are a list.
  """
  with open(csvFile, "wb") as f:
    writer = csv.writer(f, delimiter=",")
    writer.writerow(headers)
    for row in xrange(len(dataDict)):
      writer.writerow(dataDict[row])
