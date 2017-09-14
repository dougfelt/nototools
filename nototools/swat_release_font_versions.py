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

"""Update version numbers of fonts for release.

You provide a file listing font names, one per line, and a root
directory (noto-source).  The font names should be the part
before the hyphen.

It finds matching .glyphs files and updates the version number
in it to be a 2.0 version number.  If the number is already a
2.0 number it does nothing, but reports it.  It also generates
a matching versionString."""


import argparse
import logging
import os
from os import path
import re
from nototools import tool_utils
from nototools import swat_release_font_names

logger = logging.getLogger(__name__)

def swat_file(src_file, dst_file, dry_run=False):
  """Modify a single glyphs file to update the versionString and
  major/minor values.  Return None or error string if error."""

  with open(src_file, 'r') as f:
    lines = f.readlines()

  vs_re = re.compile(r'value = "Version (\d\.\d{3})";')
  saw_vs = False
  major_ix = -1
  major_version = None
  minor_ix = -1
  minor_version = None
  version_string_ix = -1
  version_string = None
  for ix, line in enumerate(lines):
    if line.startswith('versionMajor = '):
      major_ix = ix
      major_version = int(line.strip()[len('versionMajor = '):-1])
    elif line.startswith('versionMinor = '):
      minor_ix = ix
      minor_version = int(line.strip()[len('versionMinor = '):-1])
    elif line.strip() == 'name = versionString;':
      saw_vs = True
    elif saw_vs:
      saw_vs = False
      m = vs_re.match(line.strip())
      if not m:
        print '# Error: did match version string (got "%s") on line %s' % (
            line.strip(), ix)
      else:
        version_string_ix = ix
        version_string = m.group(1)

  if major_version is None or minor_version is None or version_string is None:
    raise Exception(
        'Error in %s: missing one of major: %s, minor: %s, string: %s' % (
            src_file, major_version, minor_version, version_string))

  mm_version_string = '%d.%03d' % (major_version, minor_version)
  if mm_version_string != version_string:
    raise Exception(
        'Error in %s: major/minor version %s does not match string %s' % (
            src_file, mm_version_string, version_string))

  if major_version >= 2:
    logger.warning('version of %s (%s) is already >= 2.000' % (
        src_file, version_string))
  else:
    new_major = 2
    new_minor = 40 if major_version == 2 else 0
    new_version = '%d.%03d' % (new_major, new_minor)
    logger.info('change version of %s from %s to %s' % (
        src_file, version_string, new_version))

    if not dry_run:
      lines[major_ix] = 'versionMajor = %d;\n' % new_major
      lines[minor_ix] = 'versionMinor = %d;\n' % new_minor
      lines[version_string_ix] = 'value = "Version %s";\n' % new_version
      tool_utils.ensure_dir_exists(path.dirname(dst_file))
      with open(dst_file, 'w') as f:
        f.write(''.join(lines))
      logger.info('wrote %s' % dst_file)


def swat_files(src_root, dst_root, families, dry_run=False):
  """Find all .glyphs files under src_root, match names in families
  against them, and for each match check the version.  Determine the
  release version, and change the versionString and version major and
  minor numbers accordingly.  Write the new files to dst_root in their
  same relative locations, or if dry_run just write the edits that would
  have been made.

  dst_root can be the same as src_root in which case the original files
  will be overwritten."""

  src_base = tool_utils.resolve_path(src_root)
  dst_base = tool_utils.resolve_path(dst_root)
  name_to_glyphs_file = swat_release_font_names.get_glyphs_files(src_base)
  for name in families:
    if not name in name_to_glyphs_file:
      logging.warning('unknown glyphs file name \'%s\'' % name)

  for name in sorted(name_to_glyphs_file):
    if not name in families:
      continue
    glyphs_file = name_to_glyphs_file[name]
    dst_file = path.join(dst_base, glyphs_file[len(src_base) + 1:])
    swat_file(glyphs_file, dst_file, dry_run)


def main():
  DEFAULT_SRC_DIR = '[source]/src'

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-s', '--src_dir', help='root dir of source files (default %s)' %
      DEFAULT_SRC_DIR, default=DEFAULT_SRC_DIR, metavar='dir')
  parser.add_argument(
      '-d', '--dst_dir', help='root dir of modified files, defaults to src_dir',
      metavar='dir')
  parser.add_argument(
      '-f', '--families', help='family names to process, prefix with \'@\' '
      'to read from file', nargs='+', metavar='name_or_file')
  parser.add_argument(
      '-n', '--dry_run', help='write no changes, just report them',
      action='store_true')
  parser.add_argument(
      '-l', '--loglevel', help='set log level, default "warning"',
      default='warning', metavar='level')
  args = parser.parse_args()

  args.families = swat_release_font_names.load_names(args.families)
  if not args.dst_dir:
    if not args.dry_run:
      print 'Overwriting files in %s' % args.src_dir
    args.dst_dir = args.src_dir
  if args.dry_run:
    print 'dry run'

  tool_utils.setup_logging(args.loglevel)

  swat_files(args.src_dir, args.dst_dir, args.families, args.dry_run)

if __name__ == '__main__':
  main()
