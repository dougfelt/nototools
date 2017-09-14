#!/usr/bin/env python
#
# Copyright 2017 Google Inc. All rights reserved.
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

"""Swat source files to ensure name id 1 (family name) is as lint
expects."""

import argparse
import logging
from collections import OrderedDict
from io import open
import os
from os import path
import re

from glyphsLib.parser import Parser
from glyphsLib.parser import Writer

from nototools import noto_fonts
from nototools import noto_names
from nototools import tool_utils

logger = logging.getLogger(__name__)

def _get_family_name(data):
  # data is escaped, so might be quoted -- unescape it
  return Parser.unescape_text(data['familyName'])


def _get_instance_name(instance_data):
  # data is escaped, so might be quoted -- unescape it
  return Parser.unescape_text(instance_data['name'])


def get_glyphs_files(root):
  """Finds the .glyphs files under root.  These are of the form
  'gNotoXXX.glyphs' or 'NotoXXX.glyphs' or 'NotoXXX-MM.glyphs' or
  'NotoXXX-ItalicMM.glyphs'.
  Skips the files prefixed with 'g', they shouldn't be there.
  Returns a map from the name (shorn of any -MM' and extension)
  to the file."""

  file_to_path = {}
  for p, subdirs, files in os.walk(root):
    for f in files:
      if not f.endswith('.glyphs'):
        continue
      name, _ = path.splitext(f)
      if name.startswith('g'):
        # marek created these from ttfs, we should not use
        continue
      elif name.endswith('-MM'):
        name = name[:-3]
      elif '-' in name and name.endswith('MM'):
        logger.info('unusual name 1: "%s"' % name)
        name = name[:-2]
      else:
        logger.info('unusual name 2 "%s"' % name)

      if name in file_to_path:
        logging.error(
            'file to path already has %s for %s, %s' % (
                file_to_path[name], name, path.join(p, f)))

      file_to_path[name] = path.join(p, f)
  return file_to_path


def _get_expected_family_name(family_name, instance_name, family_to_name_info):
  # synthesize a file name, get the notofont for it, then use that to get
  # the info and extract the expected name.  very hacky.
  filename = ('unhinted/%s-%s.ttf' % (family_name, instance_name)).replace(
      ' ', '')
  noto_font = noto_fonts.get_noto_font(filename)
  if not noto_font:
    return None
  name_data = noto_names.name_table_data(noto_font, family_to_name_info, 3)
  if not name_data:
    raise None
  expected = name_data.original_family
  if len(expected) > 32:
    raise Exception('name "%s" too long (%d)' % (expected, len(expected)))
  return expected


def _set_expected_family_name(family_name, instance_data):
  """Return true if we change or add styleMapFamilyName."""
  KEY = 'styleMapFamilyName'

  # data was escaped, so ensure family_name is
  family_name = Writer.escape_text(family_name)

  params = instance_data['customParameters']
  for param in params:
    if param['name'] == KEY:
      if param['value'] == family_name:
        logging.warning('family name %s already set' % family_name)
        return False
      param['value'] = family_name
      return True

  params.append(OrderedDict({'name': KEY, 'value': family_name}))
  return True


def swat_file(glyphs_file, family_to_name_info, dst_file, dry_run=False):
  """Modify a single glyphs file if any instance would have a family name
  other than the expected family name."""

  with open(glyphs_file, 'rb') as f:
    p = Parser(unescape=False)
    data = p.parse(f.read())

  modified = False
  family_name = _get_family_name(data)

  for instance_data in data['instances']:
    instance_name = _get_instance_name(instance_data)
    expected_family_name = _get_expected_family_name(
        family_name, instance_name, family_to_name_info)
    if not expected_family_name:
      logging.debug('no expected name data for %s %s' % (
          family_name, instance_name))
      continue
    if expected_family_name != family_name:
      if _set_expected_family_name(expected_family_name, instance_data):
        if dry_run:
          if not modified:
            logging.debug('editing %s' % dst_file)
          logging.debug('  change name from "%s" to "%s"' % (
              family_name, expected_family_name))
        modified = True

  if modified:
    if dry_run:
      print 'would write %s' % dst_file
    else:
      tool_utils.ensure_dir_exists(path.dirname(dst_file))
      logging.info('writing %s' % dst_file)
      with open(dst_file, 'wb') as f:
        w = Writer(out=f, escape=False)
        w.write(data)


def swat_files(src_root, dst_root, families=None, dry_run=False):
  """Find all .glyphs files under src_root, match names in families against
  them, and for each match check the instances.  Determine the expected
  family name and add styleMapFamilyName to the customParameters if needed.
  Write the new glyphs file to dst_root, or if dry_run just write what edits
  would be made.

  If families is empty then process all glyphs files found.  Output paths
  under dst_root match those under src_root.  dst_root can be the same
  as src_root in which case the original files will be overwritten.
  """

  src_base = tool_utils.resolve_path(src_root)
  dst_base = tool_utils.resolve_path(dst_root)
  family_to_name_info = noto_names.family_to_name_info_for_phase(3)
  name_to_glyphs_file = get_glyphs_files(src_base)
  for name in sorted(name_to_glyphs_file):
    if families and not name in families:
     continue
    glyphs_file = name_to_glyphs_file[name]
    dst_file = path.join(dst_base, glyphs_file[len(src_base) + 1:])

    swat_file(glyphs_file, family_to_name_info, dst_file, dry_run)


def rewrite_files(src_root, dst_root, families=None):
  """read/write the files with no other changes"""
  src_base = tool_utils.resolve_path(src_root)
  dst_base = tool_utils.resolve_path(dst_root)
  name_to_glyphs_file = get_glyphs_files(src_root)
  parser = Parser(unescape=False)
  for name in sorted(name_to_glyphs_file):
    if families and not name in families:
      continue
    glyphs_file = name_to_glyphs_file[name]
    dst_file = path.join(dst_base, glyphs_file[len(src_base) + 1:])
    logging.info('loading %s' % dst_file)
    with open(glyphs_file, 'r', encoding='utf-8') as f:
      data = parser.parse(f.read())
      tool_utils.ensure_dir_exists(path.dirname(dst_file))
    logging.info('regenerating %s' % dst_file)
    with open(dst_file, 'w', encoding='utf-8') as f:
      Writer(f, escape=False).write(data)



def load_names(names):
  """Names is a list of strings, any of which might be preceded by '@'. If
  so it is the name of a file containing a similar list of strings, one per
  line, with '#' as a comment-to-end-of-line char.  Strip comments and leading
  and trailing whitespace from each string, and return the set of unique
  non-empty strings that results."""

  result = set()
  def from_file(filename):
    with open(filename, 'r') as f:
      for name in f.readlines():
        ix = name.find('#')
        if ix != -1:
          name = name[:ix]
        addname(name)

  def addname(name):
    name = name.strip()
    if name:
      if name[0] == '@':
        from_file(name[1:])
      else:
        result.add(name)

  if names:
    for name in names:
      addname(name)

  return sorted(result)


def main():
  DEFAULT_SRC_DIR = '[source]/src'
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-s', '--src_dir', help='root dir of source files (default %s)' %
      DEFAULT_SRC_DIR, default=DEFAULT_SRC_DIR, metavar='dir')
  parser.add_argument(
      '-d', '--dst_dir', help='root dir of destination files', metavar='dir')
  parser.add_argument(
      '-f', '--families', help='family names to process, omit for all, prefix '
      'with \'@\' to read from file', nargs='+', metavar='name_or_file')
  parser.add_argument(
      '-n', '--dry_run', help='show changes without changing files',
      action='store_true')
  parser.add_argument(
      '--regen_only', help='read/write the glyphs files with no other mods, to '
      'ensure read/write code is ok.', action='store_true')
  parser.add_argument(
      '-l', '--loglevel', help='set log level, default "warning"',
      default='warning')
  args = parser.parse_args()

  args.families = load_names(args.families)
  if not args.dst_dir:
    if not args.dry_run:
      print 'Overwriting files in %s' % args.src_dir
    args.dst_dir = args.src_dir
  if args.dry_run:
    print 'dry run'

  tool_utils.setup_logging(args.loglevel)

  if args.regen_only:
    if args.dry_run:
      raise Exception('no dry run if regen_only')
    print 'regen only'
    rewrite_files(args.src_dir, args.dst_dir, args.families)
  else:
    swat_files(
        args.src_dir, args.dst_dir, args.families, args.dry_run)


if __name__ == '__main__':
  main()
