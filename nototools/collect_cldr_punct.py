#!/usr/bin/python
#
# Copyright 2016 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tool to collect some additional character usage data from cldr."""

# Punctuation used with a language that we want to investigate includes
# ellipsis, delimiters (quote start/end), and separators in list patterns.
# If cldr specifies characters here, we want to require it in the fonts.

import collections
import glob
import os
from os import path
import xml.etree.cElementTree as ET

from nototools import unicode_data
from nototools import cldr_data
from nototools import tool_utils

TOOLS_DIR = path.abspath(path.join(path.dirname(__file__), os.pardir))
CLDR_DIR = path.join(TOOLS_DIR, 'third_party', 'cldr')


def _add_text(chars, text):
  skip = False
  for i in range(len(text)):
    cp = text[i]
    if cp == '{':
      skip = True
      continue
    if cp == '}':
      skip = False
      continue
    if not skip:
      if cp == ' ':
        continue
      script = unicode_data.script(cp)
      if script == 'Zyyy':
        chars.add(cp)


def _collect_punct_data(filepath):
  tree = ET.parse(filepath)
  filename = path.basename(filepath)
  chars = set()
  for tag in tree.findall('characters/ellipsis'):
    _add_text(chars, tag.text)
  for tag in tree.findall('characters/moreInformation'):
    _add_text(chars, tag.text)
  for tag in tree.findall('delimiters'):
    for t in tag:
      _add_text(chars, t.text)
  for tag in tree.findall('listPatterns/listPattern/listPatternPart'):
    _add_text(chars, tag.text)
  return chars


def _build_script_to_punct():
  script_to_punct = collections.defaultdict(set)
  search = path.join(CLDR_DIR, 'common', 'main', '*.xml')
  files = glob.glob(search)
  for f in files:
    chars = _collect_punct_data(f)
    if chars:
      filename = path.splitext(path.basename(f))[0]
      script = cldr_data.get_likely_script(filename)
      if script == 'Zzzz':
        print 'no script for %s' % filename
      else:
          script_to_punct[script] |= chars

  script_to_punct['LGC'] = set(
      script_to_punct['Latn'] |
      script_to_punct['Grek'] |
      script_to_punct['Cyrl'])
  return script_to_punct


def _write_script_to_punct(script_to_punct):
  print 'SCRIPT_TO_PUNCT = {'
  for script in sorted(script_to_punct):
    chars = script_to_punct[script]
    int_chars = [ord(cp) for cp in chars]
    print "  # %s" % ('|'.join(sorted(chars)))
    print "  '%s': '%s'," % (script, tool_utils.write_int_ranges(int_chars))
  print '}'


def main():
  _write_script_to_punct(_build_script_to_punct())


if __name__ == "__main__":
    main()
