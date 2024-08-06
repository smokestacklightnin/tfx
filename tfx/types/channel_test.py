# Copyright 2019 Google LLC. All Rights Reserved.
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
"""Tests for tfx.utils.channel."""

from unittest import mock

import tensorflow as tf
from tfx.dsl.components.base.testing import test_node
from tfx.dsl.input_resolution import resolver_op
from tfx.dsl.placeholder import placeholder
from tfx.types import artifact
from tfx.types import channel
from tfx.types import resolved_channel

from google.protobuf import struct_pb2
from ml_metadata.proto import metadata_store_pb2


class _MyType(artifact.Artifact):
  TYPE_NAME = 'MyTypeName'
  PROPERTIES = {
      'string_value': artifact.Property(artifact.PropertyType.STRING),
      'proto_value': artifact.Property(
          artifact.PropertyType.PROTO
      ),  # Expected proto type: google.protobuf.Value
  }


class _AnotherType(artifact.Artifact):
  TYPE_NAME = 'AnotherTypeName'


class ChannelTest(tf.test.TestCase):

  def testValidChannel(self):
    instance_a = _MyType()
    instance_b = _MyType()
    chnl = channel.Channel(_MyType).set_artifacts([instance_a, instance_b])
    self.assertEqual(chnl.type_name, 'MyTypeName')
    self.assertCountEqual(chnl.get(), [instance_a, instance_b])

  def testInvalidChannelType(self):
    instance_a = _MyType()
    instance_b = _MyType()
    with self.assertRaises(ValueError):
      channel.Channel(_AnotherType).set_artifacts([instance_a, instance_b])

  def testJsonRoundTrip(self):
    proto_property = metadata_store_pb2.Value()
    proto_property.proto_value.Pack(
        struct_pb2.Value(string_value='proto-string-val'))
    chnl = channel.Channel(
        type=_MyType,
        additional_properties={
            'string_value': metadata_store_pb2.Value(string_value='forty-two'),
            'proto_value': proto_property,
        },
        additional_custom_properties={
            'int_value': metadata_store_pb2.Value(int_value=42)
        })
    serialized = chnl.to_json_dict()
    rehydrated = channel.Channel.from_json_dict(serialized)
    self.assertIs(chnl.type, rehydrated.type)
    self.assertEqual(chnl.type_name, rehydrated.type_name)
    self.assertEqual(chnl.additional_properties,
                     rehydrated.additional_properties)
    self.assertEqual(chnl.additional_custom_properties,
                     rehydrated.additional_custom_properties)

  def testJsonRoundTripUnknownArtifactClass(self):
    chnl = channel.Channel(type=_MyType)

    serialized = chnl.to_json_dict()
    serialized['type']['name'] = 'UnknownTypeName'

    rehydrated = channel.Channel.from_json_dict(serialized)
    self.assertEqual('UnknownTypeName', rehydrated.type_name)
    self.assertEqual(chnl.type._get_artifact_type().properties,
                     rehydrated.type._get_artifact_type().properties)
    self.assertTrue(rehydrated.type._AUTOGENERATED)

  def testFutureProducesPlaceholder(self):
    chnl = channel.OutputChannel(
        artifact_type=_MyType,
        producer_component=test_node.TestNode('producer'),
        output_key='foo',
    )
    future = chnl.future()
    self.assertIsInstance(future, placeholder.ChannelWrappedPlaceholder)
    self.assertIs(future.channel, chnl)
    self.assertIsInstance(future[0], placeholder.Placeholder)
    self.assertIsInstance(future.value, placeholder.Placeholder)

  def testFuturePlaceholderEquality(self):
    # The Cond() implementation in CondContext::validate() relies on placeholder
    # equality (and non-equality).
    producer = mock.MagicMock()
    producer.id = 'x1'
    future1 = channel.OutputChannel(
        artifact_type=_MyType, producer_component=producer, output_key='output1'
    ).future()
    future2 = channel.OutputChannel(
        artifact_type=_MyType, producer_component=producer, output_key='output2'
    ).future()
    self.assertTrue(future1.internal_equals(future1))
    self.assertFalse(future1.internal_equals(future2))
    self.assertTrue(future1[0].value.internal_equals(future1[0].value))
    self.assertFalse(future1[0].value.internal_equals(future2[0].value))
    self.assertTrue(future1[0].uri.internal_equals(future1[0].uri))
    self.assertFalse(future1[0].uri.internal_equals(future2[0].uri))
    self.assertTrue(future1.value.internal_equals(future1.value))
    self.assertFalse(future1.value.internal_equals(future2.value))
    pred1 = future1.value != '0'
    pred2 = future1.value != '0'
    self.assertTrue(pred1.internal_equals(pred2))
    pred3 = future2.value != '0'
    self.assertFalse(pred1.internal_equals(pred3))

  def testValidUnionChannel(self):
    channel1 = channel.Channel(type=_MyType)
    channel2 = channel.Channel(type=_MyType)
    union_channel = channel.union([channel1, channel2])
    self.assertIs(union_channel.type_name, 'MyTypeName')
    self.assertEqual(union_channel.channels, [channel1, channel2])

    union_channel = channel.union([channel1, channel.union([channel2])])
    self.assertIs(union_channel.type_name, 'MyTypeName')
    self.assertEqual(union_channel.channels, [channel1, channel2])

  def testMismatchedUnionChannelType(self):
    chnl = channel.Channel(type=_MyType)
    another_channel = channel.Channel(type=_AnotherType)
    with self.assertRaises(TypeError):
      channel.union([chnl, another_channel])

  def testEmptyUnionChannel(self):
    with self.assertRaises(ValueError):
      channel.union([])

  def testAsOutputChannel(self):
    node1 = mock.MagicMock()
    node1.id = 'n1'
    ch1 = channel.Channel(type=_MyType)
    ch1.additional_properties['string_value'] = 'foo'
    ch1.additional_custom_properties['another_string_value'] = 'bar'
    ch2 = ch1.as_output_channel(node1, 'x')

    with self.subTest('Expected Attributes'):
      self.assertEqual(ch2.type, _MyType)
      self.assertEqual(ch2.additional_properties, {'string_value': 'foo'})
      self.assertEqual(ch2.additional_custom_properties,
                       {'another_string_value': 'bar'})
      self.assertEqual(ch2.producer_component_id, 'n1')
      self.assertEqual(ch2.output_key, 'x')

    with self.subTest('AdditionalProperty Mutation'):
      ch1.additional_properties['string_value'] = 'foo2'
      ch1.additional_custom_properties['another_string_value'] = 'bar2'
      self.assertEqual(ch2.additional_properties, {'string_value': 'foo2'})
      self.assertEqual(ch2.additional_custom_properties,
                       {'another_string_value': 'bar2'})

  def testGetDataDependentNodeIds(self):
    x1 = mock.MagicMock()
    x1.id = 'x1'
    x2 = mock.MagicMock()
    x2.id = 'x2'
    p = mock.MagicMock()
    p.id = 'p'

    just_channel = channel.Channel(type=_MyType)
    output_channel_x1 = channel.OutputChannel(
        artifact_type=_MyType, producer_component=x1,
        output_key='out1')
    output_channel_x2 = channel.OutputChannel(
        artifact_type=_MyType, producer_component=x2,
        output_key='out1')
    pipeline_input_channel = channel.PipelineInputChannel(
        output_channel_x1, output_key='out2')
    pipeline_output_channel = channel.PipelineOutputChannel(
        output_channel_x2, p, output_key='out3')
    pipeline_input_channel.pipeline = p
    union_channel = channel.union([output_channel_x1, output_channel_x2])
    resolved_channel_ = resolved_channel.ResolvedChannel(
        _MyType, resolver_op.InputNode(union_channel))

    def check(ch, expected):
      with self.subTest(channel_type=type(ch).__name__):
        actual = list(ch.get_data_dependent_node_ids())
        self.assertCountEqual(
            actual, expected, f'Expected {expected} but got {actual}.')

    check(just_channel, [])
    check(output_channel_x1, ['x1'])
    check(output_channel_x2, ['x2'])
    check(pipeline_input_channel, ['p'])
    check(pipeline_output_channel, ['p'])
    check(union_channel, ['x1', 'x2'])
    check(resolved_channel_, ['x1', 'x2'])

  def testChannelAsOptionalChannel(self):
    x1 = mock.MagicMock()
    x1.id = 'x1'
    required_output_channel = channel.OutputChannel(
        artifact_type=_MyType, producer_component=x1, output_key='out1'
    )
    optional_output_channel = required_output_channel.as_optional()

    self.assertIsNone(required_output_channel.is_optional)
    self.assertTrue(optional_output_channel.is_optional)

    self.assertEqual(
        required_output_channel.producer_component,
        optional_output_channel.producer_component,
    )

    # Check new channel mutation doesn't impact parent channel
    optional_output_channel.set_as_async_channel()
    self.assertTrue(optional_output_channel.is_async)
    self.assertFalse(required_output_channel.is_async)


