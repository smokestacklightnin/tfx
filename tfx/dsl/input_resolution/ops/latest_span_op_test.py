# Copyright 2022 Google LLC. All Rights Reserved.
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
"""Tests for tfx.dsl.input_resolution.ops.latest_span_op."""

from typing import Sequence

import tensorflow as tf
from tfx import types
from tfx.dsl.input_resolution.ops import ops
from tfx.dsl.input_resolution.ops import test_utils
from tfx.types import artifact


class ArtifactWithoutSpanOrVersion(types.Artifact):
  """An Artifact without "span" or "version" as a PROPERTY."""

  TYPE_NAME = 'ArtifactWithoutSpanOrVersion'


class ArtifactWithoutSpan(types.Artifact):
  """An Artifact without "span" as a PROPERTY."""

  TYPE_NAME = 'ArtifactWithoutSpan'

  PROPERTIES = {
      'version': artifact.Property(type=artifact.PropertyType.INT),
  }


class LatestSpanOpTest(tf.test.TestCase):

  def _latest_span(self, *args, **kwargs):
    return test_utils.strict_run_resolver_op(
        ops.LatestSpan, args=args, kwargs=kwargs
    )

  def _get_artifacts_for_rolling_range_tests(self) -> Sequence[types.Artifact]:
    a10 = test_utils.DummyArtifact()
    a20 = test_utils.DummyArtifact()
    a31 = test_utils.DummyArtifact()
    a30 = test_utils.DummyArtifact()
    a71 = test_utils.DummyArtifact()
    a82 = test_utils.DummyArtifact()

    artifacts = [a10, a20, a31, a30, a71, a82]

    spans = [1, 2, 3, 3, 7, 8]
    versions = [0, 0, 1, 0, 1, 2]
    for dummy_artifact, span, version in zip(artifacts, spans, versions):
      dummy_artifact.span = span
      dummy_artifact.version = version

    return artifacts

  def testLatestSpan_Empty(self):
    actual = self._latest_span([])
    self.assertEqual(actual, [])

  def testLatestSpan_SingleEntry(self):
    a1 = test_utils.DummyArtifact()
    a1.span = 1

    actual = self._latest_span([a1])
    self.assertEqual(actual, [a1])

  def testLatestSpan_Simple(self):
    a1 = test_utils.DummyArtifact()
    a2 = test_utils.DummyArtifact()
    a3 = test_utils.DummyArtifact()
    a4 = test_utils.DummyArtifact()
    a5 = ArtifactWithoutSpan()
    a6 = ArtifactWithoutSpanOrVersion()

    a1.span = 1
    a2.span = 2
    a3.span = 2
    a4.span = 3

    a1.version = 1
    a2.version = 1
    a3.version = 2
    a4.version = 1
    a5.version = 1

    artifacts = [a1, a2, a3, a4, a5, a6]

    actual = self._latest_span(artifacts, n=1)
    self.assertEqual(actual, [a4])

    actual = self._latest_span(artifacts, n=2)
    self.assertEqual(actual, [a3, a4])

    actual = self._latest_span(artifacts, n=2, keep_all_versions=True)
    self.assertEqual(actual, [a2, a3, a4])

    actual = self._latest_span(artifacts, n=3)
    self.assertEqual(actual, [a1, a3, a4])

    actual = self._latest_span(
        [a1, a2, a3, a4, a5], n=3, keep_all_versions=True
    )
    self.assertEqual(actual, [a1, a2, a3, a4])

    actual = self._latest_span([a1, a2, a3, a4, a5], n=4)
    self.assertEqual(actual, [a1, a3, a4])

    actual = self._latest_span(
        [a1, a2, a3, a4, a5], n=4, keep_all_versions=True
    )
    self.assertEqual(actual, [a1, a2, a3, a4])

    actual = self._latest_span([a1, a2, a3, a4, a5], n=-1)
    self.assertEqual(actual, [a1, a3, a4])

    actual = self._latest_span([a1, a2, a3, a4, a5], n=-1)
    self.assertEqual(actual, [a1, a3, a4])

    actual = self._latest_span(
        [a1, a2, a3, a4, a5], n=-1, keep_all_versions=True
    )
    self.assertEqual(actual, [a1, a2, a3, a4])

  def testLatestSpan_AllSameSpanSameVersion(self):
    a1 = test_utils.DummyArtifact()
    a2 = test_utils.DummyArtifact()
    a3 = test_utils.DummyArtifact()

    a1.span = 1
    a2.span = 1
    a3.span = 1

    a1.version = 1
    a2.version = 1
    a3.version = 1

    a1.id = 1
    a2.id = 2
    a3.id = 3

    artifacts = [a1, a2, a3]

    actual = self._latest_span(artifacts, n=1)
    self.assertEqual(actual, [a3])

    actual = self._latest_span(artifacts, n=1, keep_all_versions=True)
    self.assertEqual(actual, [a1, a2, a3])

  def testLatestSpan_SkipLastN(self):
    artifacts = self._get_artifacts_for_rolling_range_tests()
    a10, a20, a31, a30, a71, a82 = artifacts

    actual = self._latest_span(artifacts)
    self.assertEqual(actual, [a82])

    actual = self._latest_span(artifacts, skip_last_n=1)
    self.assertEqual(actual, [a71])

    actual = self._latest_span(artifacts, skip_last_n=2)
    self.assertEqual(actual, [a31])

    # Tests version conflicts when keep_all_versions=False
    actual = self._latest_span(artifacts, skip_last_n=2, n=2)
    self.assertEqual(actual, [a20, a31])

    # Tests version conflicts when keep_all_versions=True. Note that 3 artifacts
    # are returned even when n=2, because n is the number of spans, NOT the
    # number of artifacts to return.
    actual = self._latest_span(
        artifacts, skip_last_n=2, n=2, keep_all_versions=True
    )
    self.assertEqual(actual, [a20, a30, a31])

    actual = self._latest_span(
        artifacts, skip_last_n=2, n=3, keep_all_versions=True
    )
    self.assertEqual(actual, [a10, a20, a30, a31])

    actual = self._latest_span(artifacts, skip_last_n=3, n=2)
    self.assertEqual(actual, [a10, a20])

    # skip_last_n=6 is larger than the number of artifacts with unique spans
    # available.
    actual = self._latest_span(artifacts, skip_last_n=6)
    self.assertEqual(actual, [])

    actual = self._latest_span(artifacts, skip_last_n=6, n=6)
    self.assertEqual(actual, [])

    # Test skip_last_n when n < 0.
    actual = self._latest_span(artifacts, n=-1, skip_last_n=2)
    self.assertEqual(actual, [a10, a20, a31])

    actual = self._latest_span(
        artifacts, n=-1, skip_last_n=2, keep_all_versions=True
    )
    self.assertEqual(actual, [a10, a20, a30, a31])

  def testLatestSpan_MinSpan(self):
    artifacts = self._get_artifacts_for_rolling_range_tests()
    _, a20, a31, a30, a71, a82 = artifacts

    # min_span=9 is greater than the largest span in artifacts, which is 8.
    actual = self._latest_span(artifacts, min_span=9)
    self.assertEqual(actual, [])

    # Although n=3, there are only 2 artifacts with a span >= 7.
    actual = self._latest_span(artifacts, min_span=7, n=3)
    self.assertEqual(actual, [a71, a82])

    # Tests version conflicts when keep_all_versions=False
    actual = self._latest_span(artifacts, min_span=2, n=3)
    self.assertEqual(actual, [a31, a71, a82])

    # Tests version conflicts when keep_all_versions=True. Note that 5 artifacts
    # are returned even when n=4, because n is the number of spans, NOT the
    # number of artifacts to return.
    actual = self._latest_span(
        artifacts, min_span=2, n=4, keep_all_versions=True
    )
    self.assertEqual(actual, [a20, a30, a31, a71, a82])

    actual = self._latest_span(
        artifacts, min_span=2, n=5, keep_all_versions=True
    )
    self.assertEqual(actual, [a20, a30, a31, a71, a82])

  def testLatestSpan_CustomVersionSortKey(self):
    rolling_range_artifacts = self._get_artifacts_for_rolling_range_tests()
    a10, a20, a31, a30, _, _ = rolling_range_artifacts

    a11 = test_utils.DummyArtifact()
    a12 = test_utils.DummyArtifact()
    a13 = test_utils.DummyArtifact()

    a11.span = 1
    a12.span = 1
    a13.span = 1

    a11.version = 1
    a12.version = 2
    a13.version = 3

    a11.mlmd_artifact.create_time_since_epoch = 100
    a12.mlmd_artifact.create_time_since_epoch = 300
    a13.mlmd_artifact.create_time_since_epoch = 200

    a11.id = 3
    a12.id = 1
    a13.id = 2
    a31.id = 31
    a30.id = 30

    artifacts = [a11, a12, a13]

    # Keys to sort the versions in a particular span.
    # Empty key string should get filtered out and does nothing
    version_sort_keys = (
        'mlmd_artifact.create_time_since_epoch',
        'id',
    )

    actual = self._latest_span(
        artifacts, n=1, version_sort_keys=version_sort_keys
    )
    self.assertEqual(actual, [a12])

    a12.mlmd_artifact.create_time_since_epoch = 200
    actual = self._latest_span(
        artifacts, n=1, version_sort_keys=version_sort_keys
    )
    self.assertEqual(actual, [a13])

    actual = self._latest_span(
        artifacts,
        n=1,
        keep_all_versions=True,
        version_sort_keys=version_sort_keys,
    )
    self.assertEqual(actual, [a11, a12, a13])

    actual = self._latest_span(
        [*artifacts, *rolling_range_artifacts],
        n=3,
        skip_last_n=2,
        keep_all_versions=True,
        version_sort_keys=version_sort_keys,
    )
    self.assertEqual(actual, [a10, a11, a12, a13, a20, a30, a31])

    actual = self._latest_span(
        [*artifacts, *rolling_range_artifacts],
        n=3,
        skip_last_n=2,
        keep_all_versions=False,
        version_sort_keys=version_sort_keys,
    )
    self.assertEqual(actual, [a13, a20, a31])

  def testLatestSpan_EmptyVersionSortKey(self):
    with self.assertRaisesRegex(
        ValueError,
        'Empty string is not allowed in version_sort_keys',
    ):
      self._latest_span(
          self._get_artifacts_for_rolling_range_tests(),
          n=1,
          version_sort_keys=('version', '', 'id'),
      )

  def testLatestSpan_AllArguments(self):
    artifacts = self._get_artifacts_for_rolling_range_tests()
    _, _, a31, a30, a71, _ = artifacts

    actual = self._latest_span(
        artifacts,
        n=5,
        skip_last_n=1,
        min_span=3,
        keep_all_versions=True,
    )
    self.assertEqual(actual, [a30, a31, a71])

    actual = self._latest_span(
        artifacts,
        n=2,
        skip_last_n=1,
        min_span=3,
        keep_all_versions=True,
    )
    self.assertEqual(actual, [a30, a31, a71])

    actual = self._latest_span(
        artifacts,
        n=1,
        skip_last_n=1,
        min_span=3,
        keep_all_versions=True,
    )
    self.assertEqual(actual, [a71])

    actual = self._latest_span(
        artifacts,
        n=-1,
        skip_last_n=2,
        min_span=3,
        keep_all_versions=True,
    )
    self.assertEqual(actual, [a30, a31])
