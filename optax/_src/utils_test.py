# Copyright 2021 DeepMind Technologies Limited. All Rights Reserved.
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
# ==============================================================================
"""Tests for `utils.py`."""

from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

import jax
import jax.numpy as jnp

from optax._src import utils


class ScaleGradientTest(parameterized.TestCase):

  @parameterized.product(inputs=[-1., 0., 1.], scale=[-0.5, 0., 0.5, 1., 2.])
  @mock.patch.object(jax.lax, 'stop_gradient', wraps=jax.lax.stop_gradient)
  def test_scale_gradient(self, mock_sg, inputs, scale):

    def fn(inputs):
      outputs = utils.scale_gradient(inputs, scale)
      return outputs ** 2

    grad = jax.grad(fn)
    self.assertEqual(grad(inputs), 2 * inputs * scale)
    if scale == 0.:
      mock_sg.assert_called_once_with(inputs)
    else:
      self.assertFalse(mock_sg.called)
    self.assertEqual(fn(inputs), inputs ** 2)

  @parameterized.product(scale=[-0.5, 0., 0.5, 1., 2.])
  def test_scale_gradient_pytree(self, scale):

    def fn(inputs):
      outputs = utils.scale_gradient(inputs, scale)
      outputs = jax.tree_util.tree_map(lambda x: x ** 2, outputs)
      return sum(jax.tree_util.tree_leaves(outputs))

    inputs = dict(a=-1., b=dict(c=(2.,), d=0.))

    grad = jax.grad(fn)
    grads = grad(inputs)
    jax.tree_util.tree_map(
        lambda i, g: self.assertEqual(g, 2 * i * scale), inputs, grads)
    self.assertEqual(
        fn(inputs),
        sum(jax.tree_util.tree_leaves(
            jax.tree_util.tree_map(lambda x: x**2, inputs))))


class MultiNormalDiagFromLogScaleTest(parameterized.TestCase):

  @staticmethod
  def _get_loc_scale(loc_shape, scale_shape):
    loc = 1.5 * jnp.ones(shape=loc_shape, dtype=jnp.float32)
    scale = 0.5 * jnp.ones(shape=scale_shape, dtype=jnp.float32)
    return loc, scale

  @parameterized.parameters(
    (1, 1, 1),
    (5, 5, 5),
    ((2, 3), (2, 3), (2, 3)),
    ((1, 4), (3, 4), (3, 4)),
    ((1, 2, 1, 3), (2, 1, 4, 3), (2, 2, 4, 3)),
  )
  def test_init_successful_broadcast(
          self, loc_shape, scale_shape, broadcasted_shape):
    def tuple_shape(shape):
      if isinstance(shape, tuple):
        return shape
      return tuple([shape])

    loc, scale = self._get_loc_scale(loc_shape, scale_shape)
    dist = utils.multi_normal(loc, scale)
    self.assertIsInstance(dist, utils.MultiNormalDiagFromLogScale)
    mean, log_scale = dist.params
    self.assertTrue(tuple(mean.shape) == tuple_shape(loc_shape))
    self.assertTrue(tuple(log_scale.shape) == tuple_shape(scale_shape))
    self.assertTrue(tuple(dist._param_shape) == tuple_shape(broadcasted_shape))

  @parameterized.parameters(
    (2, 3),
    ((2, 3), (3, 2)),
    ((2, 4), (3, 4)),
    ((1, 2, 1, 3), (2, 1, 4, 4)),
  )
  def test_init_unsuccessful_broadcast(self, loc_shape, scale_shape):
    loc, scale = self._get_loc_scale(loc_shape, scale_shape)
    with self.assertRaises(ValueError):
      utils.multi_normal(loc, scale)

  @parameterized.parameters(list, tuple)
  def test_sample_input_sequence_types(self, sample_type):
    sample_shape = sample_type((4, 5))
    loc_shape = scale_shape = (2, 3)
    loc, scale = self._get_loc_scale(loc_shape, scale_shape)
    dist = utils.multi_normal(loc, scale)
    samples = dist.sample(sample_shape, jax.random.PRNGKey(239))
    self.assertTrue(samples.shape == tuple(sample_shape) + loc_shape)

  @parameterized.named_parameters([
    ('1d', 1),
    ('2d', (2, 3)),
    ('4d', (1, 2, 3, 4)),
  ])
  def test_log_prob(self, shape):
    loc, scale = self._get_loc_scale(shape, shape)
    dist = utils.multi_normal(loc, scale)
    probs = dist.log_prob(jnp.ones(shape=shape, dtype=jnp.float32))

    self.assertIsInstance(probs, jnp.DeviceArray)
    self.assertFalse(bool(probs.shape))


if __name__ == '__main__':
  absltest.main()
