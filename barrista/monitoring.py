# -*- coding: utf-8 -*-
"""Defines several tools for monitoring net activity."""
# pylint: disable=F0401, E1101, too-many-lines, wrong-import-order
import logging as _logging
import os as _os
import time as _time
import subprocess as _subprocess
import collections as _collections
import numpy as _np
# pylint: disable=no-name-in-module
from scipy.stats import bernoulli as _bernoulli
from scipy.ndimage.interpolation import rotate as _rotate
from sklearn.decomposition import PCA as _PCA
from .tools import pad as _pad

# CAREFUL! This must be imported before any caffe-related import!
from .initialization import init as _init

import caffe as _caffe
try:  # pragma: no cover
    import cv2 as _cv2
    _cv2INTER_CUBIC = _cv2.INTER_CUBIC  # pylint: disable=invalid-name
    _cv2INTER_LINEAR = _cv2.INTER_LINEAR  # pylint: disable=invalid-name
    _cv2INTER_NEAREST = _cv2.INTER_NEAREST  # pylint: disable=invalid-name
    _cv2resize = _cv2.resize  # pylint: disable=invalid-name
except ImportError:  # pragma: no cover
    _cv2 = None
    _cv2INTER_CUBIC = None  # pylint: disable=invalid-name
    _cv2INTER_LINEAR = None  # pylint: disable=invalid-name
    _cv2INTER_NEAREST = None  # pylint: disable=invalid-name
    _cv2resize = None  # pylint: disable=invalid-name
try:  # pragma: no cover
    import matplotlib.pyplot as _plt
    import matplotlib.ticker as _tkr
    import matplotlib.colorbar as _colorbar
    from mpl_toolkits.axes_grid1 import make_axes_locatable as _make_axes_locatable
    _PLT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLT_AVAILABLE = False
_init()
_LOGGER = _logging.getLogger(__name__)


class Monitor(object):  # pylint: disable=R0903

    """
    The monitor interface.

    Should be implemented by any monitor class. The method
    :py:func:`barrista.monitoring.Monitor.__call__` must be specified,
    the function :py:func:`barrista.monitoring.Monitor.finalize` may
    optionally be specified.
    """

    def __call__(self, kwargs):
        """
        The call implementation.

        For available keyword arguments, see the documentation of
        :py:class:`barrista.solver.SolverInterface.Fit`.

        The callback signals are used as follows:
        * initialize_train: called once before training starts,
        * initialize_test: called once before training starts (if training with
          a validation set is used) or once before testing,
        * pre_fit: called before fitting mode is used (e.g., before going
          back to fitting during training after a validation run),
        * pre_test: called before testing mode is used (e.g., during training
          before validation starts),
        * post_test: called when testing finished,
        * pre_train_batch: before a training batch is fed to the network,
        * post_train_batch: after forwarding a training batch,
        * pre_test_batch: before a test batch is fed to the network,
        * post_test_batch: after a test batch was forwarded through the
          network.
        """
        if kwargs['callback_signal'] == 'initialize_train':
            self._initialize_train(kwargs)
        elif kwargs['callback_signal'] == 'initialize_test':
            self._initialize_test(kwargs)
        elif kwargs['callback_signal'] == 'pre_fit':
            self._pre_fit(kwargs)
        elif kwargs['callback_signal'] == 'pre_test':
            self._pre_test(kwargs)
        elif kwargs['callback_signal'] == 'post_test':
            self._post_test(kwargs)
        elif kwargs['callback_signal'] == 'pre_test_batch':
            self._pre_test_batch(kwargs)
        elif kwargs['callback_signal'] == 'post_test_batch':
            self._post_test_batch(kwargs)
        elif kwargs['callback_signal'] == 'pre_train_batch':
            self._pre_train_batch(kwargs)
        elif kwargs['callback_signal'] == 'post_train_batch':
            self._post_train_batch(kwargs)

    def _initialize_train(self, kwargs):  # pylint: disable=C0111
        pass

    def _initialize_test(self, kwargs):  # pylint: disable=C0111
        pass

    def _pre_fit(self, kwargs):  # pylint: disable=C0111
        pass

    def _pre_test(self, kwargs):  # pylint: disable=C0111
        pass

    def _post_test(self, kwargs):  # pylint: disable=C0111
        pass

    def _pre_test_batch(self, kwargs):  # pylint: disable=C0111
        pass

    def _post_test_batch(self, kwargs):  # pylint: disable=C0111
        pass

    def _pre_train_batch(self, kwargs):  # pylint: disable=C0111
        pass

    def _post_train_batch(self, kwargs):  # pylint: disable=C0111
        pass

    def finalize(self, kwargs):
        """Will be called at the end of a training/fitting process."""
        pass


class DataMonitor(Monitor):  # pylint: disable=R0903

    r"""
    Monitor interface for filling the blobs of a network.

    This is a specific monitor which will fill the blobs of the network
    for the forward pass or solver step.
    Ideally, there should only be one such monitor per callback,
    but multiple ones are possible.
    """

    pass


class ParallelMonitor(Monitor):

    r"""
    Monitor interface for monitors executed parallel to processing a batch.

    The order of all monitors implementing this interface is respected. They
    will work on a dummy network object with dummy blobs and prepare their
    data. The dummy blob content is then copied to the real network prior
    to the next batch execution.
    """

    def get_parallel_blob_names(self):  # pragma: no cover
        """Get the names of all blobs that must be provided for the dummy."""
        raise NotImplementedError()


# pylint: disable=too-few-public-methods
class StaticDataMonitor(DataMonitor, ParallelMonitor):

    r"""
    Always provides the same data for a specific net input blob.

    Parameters
    ==========

    :param X: dict(string, np.ndarray)
      The static input blobs to use.
    """

    def __init__(self, X):
        self._X = X  # pylint: disable=C0103

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']


        for key, value in list(self._X.items()):
            assert key in list(net.blobs.keys()), (
                'data key has no corresponding network blob {} {}'.format(
                    key, str(list(net.blobs.keys()))))
            assert isinstance(value, _np.ndarray), (
                'data must be a numpy nd array ({})'.format(type(value))
            )

    def _pre_train_batch(self, kwargs):
        self._pre_batch(kwargs['net'], kwargs)

    def _pre_test_batch(self, kwargs):
        self._pre_batch(kwargs['testnet'], kwargs)

    def _pre_batch(self, net, kwargs):  # pylint: disable=unused-argument
        for key in list(self._X.keys()):
            net.blobs[key].data[...] = self._X[key]

    def get_parallel_blob_names(self):
        """Get the names of all blobs that must be provided for the dummy."""
        return list(self._X.keys())



# pylint: disable=too-few-public-methods
class OversamplingDataMonitor(DataMonitor, ParallelMonitor):

    r"""
    Provides oversampled data.

    Parameters
    ==========

    :param blobinfos: dict(string, string|None).
      Associates blob name to oversample and optional the interpolation
      method to use for resize. This may be 'n' (nearest neighbour),
      'c' (cubic), 'l' (linear) or None (no interpolation). If an
      interpolation method is selected, `before_oversample_resize_to` must
      be not None and provide a size.

    :param before_oversample_resize_to: dict(string, 2-tuple).
      Specifies a size to which the image inputs will be resized before the
      oversampling is invoked.
    """

    def __init__(self,
                 blobinfos,
                 before_oversample_resize_to=None):
        for val in blobinfos.values():
            assert val in ['n', 'c', 'l', None]
        self._blobinfos = blobinfos
        for key, val in blobinfos.items():
            if val is not None:
                assert key in list(before_oversample_resize_to.keys())
        self._before_oversample_resize_to = before_oversample_resize_to
        self._batch_size = None

    def get_parallel_blob_names(self):
        """Get the names of all blobs that must be provided for the dummy."""
        return list(self._blobinfos.keys())

    def _initialize_train(self, kwargs):
        raise Exception("The OversamplingDataMonitor can only be used during "
                        "testing!")

    def _initialize_test(self, kwargs):
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']

        for key in list(self._blobinfos.keys()):
            assert key in list(net.blobs.keys()), (
                'data key has no corresponding network blob {} {}'.format(
                    key, str(list(net.blobs.keys()))))

    def _pre_test(self, kwargs):  # pragma: no cover
        net = kwargs['testnet']
        self._batch_size = net.blobs[
            list(self._blobinfos.keys())[0]].data.shape[0]

    def _pre_test_batch(self, kwargs):  # pragma: no cover
        for blob_name in list(self._blobinfos):
            assert blob_name in kwargs['data_orig'], (
                "The unchanged data must be provided by another DataProvider, "
                "e.g., CyclingDataMonitor with `only_preload`!")
            assert (len(kwargs['data_orig'][blob_name]) * 10 ==
                    self._batch_size), (
                        "The number of provided images * 10 must be the batch "
                        "size!")
            # pylint: disable=invalid-name
            for im_idx, im in enumerate(kwargs['data_orig'][blob_name]):
                if self._blobinfos[blob_name] is not None:
                    if self._blobinfos[blob_name] == 'n':
                        interpolation = _cv2INTER_NEAREST
                    elif self._blobinfos[blob_name] == 'c':
                        interpolation = _cv2INTER_CUBIC
                    elif self._blobinfos[blob_name] == 'l':
                        interpolation = _cv2INTER_LINEAR
                    oversampling_prep = _cv2resize(
                        _np.transpose(im, (1, 2, 0)),
                        (self._before_oversample_resize_to[blob_name][1],
                         self._before_oversample_resize_to[blob_name][0]),
                        interpolation=interpolation)
                else:
                    oversampling_prep = _np.transpose(im, (1, 2, 0))
                imshape = kwargs['testnet'].blobs[blob_name].data.shape[2:4]
                kwargs['testnet'].blobs[blob_name].data[
                    im_idx * 10:(im_idx+1) * 10] =\
                        _np.transpose(
                            _caffe.io.oversample(
                                [oversampling_prep],
                                imshape),
                            (0, 3, 1, 2))


# pylint: disable=too-many-instance-attributes, R0903
class CyclingDataMonitor(DataMonitor, ParallelMonitor):

    r"""
    Uses the data sequentially.

    This monitor maps data to the network an cycles through the data
    sequentially. It is the default monitor used if a user provides X
    or X_val to the barrista.solver.fit method.

    If further processing of the original data is intended, by using the flag
    ``only_preload``, the following monitors find a dictionary of lists of
    the original datapoints with the name 'data_orig' in their ``kwargs``.
    The data is in this case NOT written to the network input layers! This
    can make sense, e.g., for the ``ResizingMonitor``.

    :param X: dict of numpy.ndarray or list,  or None.
      If specified, is used as input data. It is used sequentially, so
      shuffle it pre, if required. The keys of the dict must have
      a corresponding layer name in the net. The values must be provided
      already in network dimension order, i.e., usually channels, height,
      width.

    :param only_preload: list(string).
      List of blobs for which the data will be loaded and stored in a dict
      of (name: list) for further processing with other monitors.

    :param input_processing_flags: dict(string, string).
      Dictionary associating input blob names with intended preprocessing
      methods. Valid values are:
        * n: none,
        * rn: resize, nearest neighbour,
        * rc: resize, cubic,
        * rl: resize, linear,
        * pX: padding, with value X.

    :param virtual_batch_size: int or None.
      Override the network batch size. May only be used if ``only_preload`` is
      set to True. Only makes sense with another DataMonitor in succession.

    :param color_data_augmentation_sigmas: dict(string, float) or None.
      Enhance the color of the samples as described in (Krizhevsky et al.,
      2012). The parameter gives the sigma for the normal distribution that is
      sampled to obtain the weights for scaled pixel principal components per
      blob.

    :param shuffle: Bool.
      If set to True, shuffle the data every epoch. Default: False.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 X,
                 only_preload=None,
                 input_processing_flags=None,
                 virtual_batch_size=None,
                 color_data_augmentation_sigmas=None,
                 shuffle=False):
        """See class documentation."""
        if only_preload is None:
            only_preload = []
        self.only_preload = only_preload
        self._X = X  # pylint: disable=C0103
        assert X is not None
        if input_processing_flags is None:
            input_processing_flags = dict()
        self._input_processing_flags = input_processing_flags
        for key in input_processing_flags.keys():
            assert key in self._X.keys()
        self._padvals = dict()
        for key, val in input_processing_flags.items():
            assert (val in ['n', 'rn', 'rc', 'rl'] or
                    val.startswith('p')), (
                        "The input processing flags for the CyclingDataMonitor "
                        "must be in ['n', 'rn', 'rc', 'rl', 'p']: {}!".format(
                            val))
            if val.startswith('p'):
                self._padvals[key] = int(val[1:])
        for key in self.only_preload:
            assert key in self._X.keys()
        self._sample_pointer = 0
        self._len_data = None
        self._initialized = False
        self._batch_size = None
        assert virtual_batch_size is None or self.only_preload, (
            "If the virtual_batch_size is set, `only_preload` must be used!")
        if virtual_batch_size is not None:
            assert virtual_batch_size > 0
        self._virtual_batch_size = virtual_batch_size
        if color_data_augmentation_sigmas is None:
            color_data_augmentation_sigmas = dict()
        self._color_data_augmentation_sigmas = color_data_augmentation_sigmas
        for key in list(self._color_data_augmentation_sigmas.keys()):
            assert key in list(self._X.keys())
        for key in list(self._X.keys()):
            if key not in list(self._color_data_augmentation_sigmas.keys()):
                self._color_data_augmentation_sigmas[key] = 0.
        # pylint: disable=invalid-name
        self._color_data_augmentation_weights = dict()
        # pylint: disable=invalid-name
        self._color_data_augmentation_components = dict()
        self._shuffle = shuffle
        self._sample_order = None

    def get_parallel_blob_names(self):
        return list(self._X.keys())

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)
        # Calculate the color channel PCA per blob if required.
        for bname, sigma in self._color_data_augmentation_sigmas.items():
            if sigma > 0.:
                _LOGGER.info("Performing PCA for color data augmentation for "
                             "blob '%s'...", bname)
                for im in self._X[bname]:  # pylint: disable=invalid-name
                    assert im.ndim == 3 and im.shape[0] == 3, (
                        "To perform the color data augmentation, images must "
                        "be provided in shape (3, height, width).")
                flldta = _np.vstack(
                    [im.reshape((3, im.shape[1] * im.shape[2])).T
                     for im in self._X[bname]])
                # No need to copy the data another time, since `vstack` already
                # copied it.
                pca = _PCA(copy=False, whiten=False)
                pca.fit(flldta)
                self._color_data_augmentation_weights[bname] = _np.sqrt(
                    pca.explained_variance_.astype('float32'))
                self._color_data_augmentation_components[bname] = \
                    pca.components_.T.astype('float32')

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):
        # we make sure, now that the network is available, that
        # all names in the provided data dict has a corresponding match
        # in the network
        if self._initialized:
            raise Exception("This DataProvider has already been intialized! "
                            "Did you maybe try to use it for train and test? "
                            "This is not possible!")
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']

        self._len_data = len(list(self._X.values())[0])
        for key, value in list(self._X.items()):
            if key not in self._input_processing_flags:
                self._input_processing_flags[key] = 'n'
            assert key in list(net.blobs.keys()), (
                'data key has no corresponding network blob {} {}'.format(
                    key, str(list(net.blobs.keys()))))
            assert len(value) == self._len_data, (
                'all items need to have the same length {} vs {}'.format(
                    len(value), self._len_data))
            assert isinstance(value, _np.ndarray) or isinstance(value, list), (
                'data must be a numpy nd array or list ({})'.format(type(value))
            )
        self._sample_order = list(range(self._len_data))
        if self._shuffle:
            _np.random.seed(1)
            self._sample_order = _np.random.permutation(self._sample_order)
        self._initialized = True

    def _pre_fit(self, kwargs):
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']
        if self._virtual_batch_size is not None:
            self._batch_size = self._virtual_batch_size
        else:
            self._batch_size = net.blobs[list(self._X.keys())[0]].data.shape[0]
        assert self._batch_size > 0

    def _pre_test(self, kwargs):
        self._pre_fit(kwargs)
        self._sample_pointer = 0

    def _pre_train_batch(self, kwargs):
        self._pre_batch(kwargs['net'], kwargs)

    def _pre_test_batch(self, kwargs):
        self._pre_batch(kwargs['testnet'], kwargs)

    def _color_augment(self, bname, sample):
        sigma = self._color_data_augmentation_sigmas[bname]
        if sigma == 0.:
            if isinstance(sample, (int, float)):
                return float(sample)
            else:
                return sample.astype('float32')
        else:
            comp_weights = _np.random.normal(0., sigma, 3).astype('float32') *\
                           self._color_data_augmentation_weights[bname]
            noise = _np.dot(self._color_data_augmentation_components[bname],
                            comp_weights.T)
            return (sample.astype('float32').transpose((1, 2, 0)) + noise)\
                .transpose((2, 0, 1))

    def _pre_batch(self, net, kwargs):  # pylint: disable=C0111, W0613, R0912
        # this will simply cycle through the data.
        samples_ids = [self._sample_order[idx % self._len_data]
                       for idx in
                       range(self._sample_pointer,
                             self._sample_pointer + self._batch_size)]
        # updating the sample pointer for the next time
        old_sample_pointer = self._sample_pointer
        self._sample_pointer = (
            (self._sample_pointer + len(samples_ids)) % self._len_data)
        if self._shuffle and old_sample_pointer > self._sample_pointer:
            # Epoch ended. Reshuffle.
            self._sample_order = _np.random.permutation(self._sample_order)

        if len(self.only_preload) > 0:
            sample_dict = dict()

        for key in list(self._X.keys()):  # pylint: disable=too-many-nested-blocks
            if key in self.only_preload:
                sample_dict[key] = []
            # this will actually fill the data for the network
            for sample_idx in range(self._batch_size):
                augmented_sample = self._color_augment(
                    key,
                    self._X[key][samples_ids[sample_idx]])
                if key in self.only_preload:
                    sample_dict[key].append(augmented_sample)
                else:
                    if (net.blobs[key].data[sample_idx].size == 1 and (
                            isinstance(self._X[key][samples_ids[sample_idx]],
                                       (int, float)) or
                            self._X[key][samples_ids[sample_idx]].size == 1) or
                            self._X[key][samples_ids[sample_idx]].size ==
                            net.blobs[key].data[sample_idx].size):
                        if net.blobs[key].data[sample_idx].size == 1:
                            net.blobs[key].data[sample_idx] =\
                                 augmented_sample
                        else:
                            net.blobs[key].data[sample_idx] = (
                                augmented_sample.reshape(
                                    net.blobs[key].data.shape[1:]))
                    else:
                        if self._input_processing_flags[key] == 'n':  # pragma: no cover
                            raise Exception(("Sample size {} does not match " +
                                             "network input size {} and no " +
                                             "preprocessing is allowed!")
                                            .format(
                                                augmented_sample.size,
                                                net.blobs[key].data[sample_idx].size))
                        elif self._input_processing_flags[key] in ['rn',
                                                                   'rc',
                                                                   'rl']:
                            assert (
                                augmented_sample.shape[0]
                                == net.blobs[key].data.shape[1])
                            if self._input_processing_flags == 'rn':
                                interp_method = _cv2INTER_NEAREST
                            elif self._input_processing_flags == 'rc':
                                interp_method = _cv2INTER_CUBIC
                            else:
                                interp_method = _cv2INTER_LINEAR
                            for channel_idx in range(
                                    net.blobs[key].data.shape[1]):
                                net.blobs[key].data[sample_idx, channel_idx] =\
                                    _cv2resize(
                                        augmented_sample[channel_idx],
                                        (net.blobs[key].data.shape[3],
                                         net.blobs[key].data.shape[2]),
                                        interpolation=interp_method)
                        else:
                            # Padding.
                            net.blobs[key].data[sample_idx] = _pad(
                                augmented_sample,
                                net.blobs[key].data.shape[2:4],
                                val=self._padvals[key])
        if len(self.only_preload) > 0:
            kwargs['data_orig'] = sample_dict


class ResizingMonitor(ParallelMonitor, Monitor):  # pylint: disable=R0903

    r"""
    Optionally resizes input data and adjusts the network input shape.

    This monitor optionally resizes the input data randomly and adjusts
    the network input size accordingly (this works only for batch size 1
    and fully convolutional networks).

    For this to work, it must be used with the ``CyclingDataMonitor`` with
    ``only_preload`` set.

    :param blobinfos: dict(string, int).
      Describes which blobs to apply the resizing operation to, and which
      padding value to use for the remaining space.

    :param base_scale: float.
      If set to a value different than 1., apply the given base scale first
      to images. If set to a value different than 1., the parameter
      ``interp_methods`` must be set.

    :param random_change_up_to: float.
      If set to a value different than 0., the scale change is altered
      randomly with a uniformly drawn value from -``random_change_up_to`` to
      ``random_change_up_to``, that is being added to the base value.

    :param net_input_size_adjustment_multiple_of: int.
      If set to a value greater than 0, the blobs shape is adjusted from its
      initial value (which is used as minimal one) in multiples of the given
      one.

    :param interp_methods: dict(string, string).
      Dictionary which stores for every blob the interpolation method. The
      string must be for each blob in ['n', 'c', 'l'] (nearest neighbour,
      cubic, linear).
    """

    def __init__(self,  # pylint: disable=R0913
                 blobinfos,
                 base_scale=1.,
                 random_change_up_to=0.,
                 net_input_size_adjustment_multiple_of=0,
                 interp_methods=None):
        """See class documentation."""
        self._blobinfos = blobinfos
        self._base_scale = base_scale
        self._random_change_up_to = random_change_up_to
        if self._base_scale != 1. or self._random_change_up_to != 0.:
            assert interp_methods is not None
            for key in self._blobinfos.keys():
                assert key in interp_methods.keys()
                assert interp_methods[key] in ['n', 'c', 'l']
        self._interp_methods = interp_methods
        self._adjustment_multiple_of = net_input_size_adjustment_multiple_of
        self._min_input_size = None
        self._batch_size = None

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):
        # we make sure, now that the network is available, that
        # all names in the provided data dict have a corresponding match
        # in the network
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']

        for key in list(self._blobinfos.keys()):
            assert key in list(net.blobs.keys()), (
                'data key has no corresponding network blob {} {}'.format(
                    key, str(list(net.blobs.keys()))))
            assert net.blobs[key].data.ndim == 4
            if self._adjustment_multiple_of > 0:
                if self._min_input_size is None:
                    self._min_input_size = net.blobs[key].data.shape[2:4]
                else:
                    assert (net.blobs[key].data.shape[2:4] ==
                            self._min_input_size), (
                                'if automatic input size adjustment is '
                                'activated, all inputs must be of same size '
                                '(first: {}, {}: {})'.format(
                                    self._min_input_size, key,
                                    net.blobs[key].data.shape[2:4]))

    def _pre_fit(self, kwargs):
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']
        self._batch_size = net.blobs[
            list(self._blobinfos.keys())[0]].data.shape[0]
        if self._adjustment_multiple_of > 0:
            assert self._batch_size == 1, (
                "If size adjustment is activated, the batch size must be one!")

    def _pre_test(self, kwargs):
        self._pre_fit(kwargs)

    def _pre_train_batch(self, kwargs):
        self._pre_batch(kwargs['net'], kwargs)

    def _pre_test_batch(self, kwargs):
        self._pre_batch(kwargs['testnet'], kwargs)

     # pylint: disable=C0111, W0613, R0912, too-many-locals
    def _pre_batch(self, net, kwargs):
        scales = None
        sizes = None
        if not 'data_orig' in kwargs.keys():
            raise Exception(
                "This data monitor needs a data providing monitor "
                "to run in advance (e.g., a CyclingDataMonitor with "
                "`only_preload`)!")
        for key, value in kwargs['data_orig'].items():
            assert len(value) == self._batch_size
            if sizes is None:
                sizes = []
                for img in value:
                    sizes.append(img.shape[1:3])
            else:
                for img_idx, img in enumerate(value):
                    # pylint: disable=unsubscriptable-object
                    assert img.shape[1:3] == sizes[img_idx]
        for key, padval in self._blobinfos.items():
            if scales is None:
                scales = []
                for sample_idx in range(self._batch_size):
                    if self._random_change_up_to > 0:
                        scales.append(
                            self._base_scale +
                            _np.random.uniform(low=-self._random_change_up_to,
                                               high=self._random_change_up_to))
                    else:
                        scales.append(self._base_scale)
            for sample_idx in range(self._batch_size):
                # Get the scaled data.
                scaled_sample = kwargs['data_orig'][key][sample_idx]
                if scales[sample_idx] != 1.:
                    scaled_sample = _np.empty((scaled_sample.shape[0],
                                               int(scaled_sample.shape[1] *
                                                   scales[sample_idx]),
                                               int(scaled_sample.shape[2] *
                                                   scales[sample_idx])),
                                              dtype='float32')
                    if self._interp_methods[key] == 'n':
                        interpolation_method = _cv2INTER_NEAREST
                    elif self._interp_methods[key] == 'l':
                        interpolation_method = _cv2INTER_LINEAR
                    else:
                        interpolation_method = _cv2INTER_CUBIC
                    for layer_idx in range(scaled_sample.shape[0]):
                        scaled_sample[layer_idx] = _cv2resize(
                            kwargs['data_orig'][key][sample_idx][layer_idx],
                            (scaled_sample.shape[2],
                             scaled_sample.shape[1]),
                            interpolation=interpolation_method)
                # If necessary, adjust the network input size.
                if self._adjustment_multiple_of > 0:
                    image_height, image_width = scaled_sample.shape[1:3]
                    netinput_height = int(max(
                        self._min_input_size[0] +
                        _np.ceil(
                            float(image_height - self._min_input_size[0]) /
                            self._adjustment_multiple_of) *
                        self._adjustment_multiple_of,
                        self._min_input_size[0]))
                    netinput_width = int(max(
                        self._min_input_size[1] +
                        _np.ceil(
                            float(image_width - self._min_input_size[1]) /
                            self._adjustment_multiple_of) *
                        self._adjustment_multiple_of,
                        self._min_input_size[1]))
                    net.blobs[key].reshape(1,
                                           scaled_sample.shape[0],
                                           netinput_height,
                                           netinput_width)
                # Put the data in place.
                net.blobs[key].data[sample_idx] = _pad(
                    scaled_sample,
                    net.blobs[key].data.shape[2:4],
                    val=padval)

    def get_parallel_blob_names(self):
        """Get the names of all blobs that must be provided for the dummy."""
        return list(self._blobinfos.keys())


# pylint: disable=too-few-public-methods
class RotatingMirroringMonitor(ParallelMonitor, Monitor):

    r"""
    Rotate and/or horizontally mirror samples within blobs.

    For every sample, the rotation and mirroring will be consistent
    across the blobs.

    :param blobinfos: dict(string, int).
      A dictionary containing the blob names and the padding values that
      will be applied.

    :param max_rotation_degrees: float.
      The rotation will be sampled uniformly from the interval
      [-rotation_degrees, rotation_degrees[ for each sample.

    :param mirror_prob: float.
      The probability that horizontal mirroring occurs. Is as well sampled
      individually for every sample.

    :param mirror_value_swaps: dict(string, dict(int, list(2-tuples))).
      Specifies for every blob for every layer whether any values must be
      swapped if mirroring is applied. This is important when, e.g.,
      mirroring annotation maps with left-right information. Every 2-tuple
      contains (original value, new value). The locations of the swaps are
      determined before any change is applied, so the order of tuples does not
      play a role.

    :param mirror_layer_swaps: dict(string, list(2-tuples)).
      Specifies for every blob whether any layers must be swapped if
      mirroring is applied. Can be used together with mirror_value_swaps: in
      this case, the `mirror_value_swaps` are applied first, then the layers
      are swapped.
    """
    # pylint: disable=too-many-arguments
    def __init__(self,
                 blobinfos,
                 max_rotation_degrees,
                 mirror_prob=0.,
                 mirror_value_swaps=None,
                 mirror_layer_swaps=None):
        """See class documentation."""
        self._blobinfos = blobinfos
        self._rotation_degrees = max_rotation_degrees
        self._mirror_prob = mirror_prob
        self._batch_size = None
        if mirror_value_swaps is None:
            mirror_value_swaps = dict()
        for key in list(mirror_value_swaps.keys()):
            assert key in self._blobinfos, ("Blob not in handled: {}!"\
                                            .format(key))
            for layer_idx in list(mirror_value_swaps[key].keys()):
                m_tochange = []
                for swappair in mirror_value_swaps[key][layer_idx]:
                    assert len(swappair) == 2, (
                        "Swaps must be specified as (from_value, to_value): {}"\
                        .format(mirror_value_swaps[key][layer_idx]))
                    assert swappair[0] not in m_tochange, (
                        "Every value may change only to one new: {}."\
                        .format(mirror_value_swaps[key][layer_idx]))
                    m_tochange.append(swappair[0])
                    assert blobinfos[key] not in swappair, (
                        "A specified swap value is the fill value for this "
                        "blob: {}, {}, {}.".format(key,
                                                   blobinfos[key][layer_idx],
                                                   swappair))
        if mirror_layer_swaps is None:
            mirror_layer_swaps = dict()
        for key in list(mirror_layer_swaps.keys()):
            assert key in self._blobinfos, ("Blob not handled: {}!"\
                                            .format(key))
            idx_tochange = []
            for swappair in mirror_layer_swaps[key]:
                assert len(swappair) == 2, (
                    "Swaps must be specified as (from_value, to_value): {}"\
                    .format(swappair))
                assert (swappair[0] not in idx_tochange and
                        swappair[1] not in idx_tochange), (
                            "Every value may only be swapped to or from one "
                            "position!")
                idx_tochange.extend(swappair)
        for key in list(self._blobinfos):
            if key not in list(mirror_value_swaps.keys()):
                mirror_value_swaps[key] = dict()
            if key not in list(mirror_layer_swaps.keys()):
                mirror_layer_swaps[key] = []
        self._mirror_value_swaps = mirror_value_swaps
        self._mirror_layer_swaps = mirror_layer_swaps

    def get_parallel_blob_names(self):
        """Get the names of all blobs that must be provided for the dummy."""
        return list(self._blobinfos.keys())

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):
        # we make sure, now that the network is available, that
        # all names in the provided data dict have a corresponding match
        # in the network
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']

        for key in list(self._blobinfos.keys()):
            assert key in list(net.blobs.keys()), (
                'data key has no corresponding network blob {} {}'.format(
                    key, str(list(net.blobs.keys()))))
            assert net.blobs[key].data.ndim == 4
            for layer_idx in self._mirror_value_swaps[key].keys():
                assert layer_idx < net.blobs[key].data.shape[1], ((
                    "The data for blob {} has not enough layers for swapping "
                    "{}!").format(key, layer_idx))
            for swappair in self._mirror_layer_swaps[key]:
                assert (swappair[0] < net.blobs[key].data.shape[1] and
                        swappair[1] < net.blobs[key].data.shape[1]), (
                            "Not enough layers in blob {} to swap {}!".format(
                                key, swappair))

    def _pre_fit(self, kwargs):
        if 'test' in kwargs['callback_signal']:
            net = kwargs['testnet']
        else:
            net = kwargs['net']
        self._batch_size = net.blobs[
            list(self._blobinfos.keys())[0]].data.shape[0]

    def _pre_test(self, kwargs):
        self._pre_fit(kwargs)

    def _pre_train_batch(self, kwargs):
        self._pre_batch(kwargs['net'], kwargs)

    def _pre_test_batch(self, kwargs):
        self._pre_batch(kwargs['testnet'], kwargs)

     # pylint: disable=C0111, W0613, R0912, too-many-locals
    def _pre_batch(self, net, kwargs):
        rotations = None
        mirrorings = None
        spline_interpolation_order = 0
        prefilter = False
        for key, padval in self._blobinfos.items():
            if rotations is None:
                rotations = []
                if self._rotation_degrees > 0.:
                    rotations = _np.random.uniform(low=-self._rotation_degrees,
                                                   high=self._rotation_degrees,
                                                   size=self._batch_size)
                else:
                    rotations = [0.] * self._batch_size
            if mirrorings is None:
                mirrorings = []
                if self._mirror_prob > 0.:
                    mirrorings = _bernoulli.rvs(self._mirror_prob,
                                                size=self._batch_size)
                else:
                    mirrorings = [0] * self._batch_size
            for sample_idx in range(self._batch_size):
                if rotations[sample_idx] != 0.:
                    net.blobs[key].data[sample_idx] = _rotate(
                        net.blobs[key].data[sample_idx],
                        rotations[sample_idx],
                        (1, 2),
                        reshape=False,
                        order=spline_interpolation_order,
                        mode='constant',
                        cval=padval,
                        prefilter=prefilter)
                if mirrorings[sample_idx] == 1.:
                    net.blobs[key].data[sample_idx] = \
                        net.blobs[key].data[sample_idx, :, :, ::-1]
                    for layer_idx in range(net.blobs[key].data.shape[1]):
                        if (layer_idx not in
                                self._mirror_value_swaps[key].keys()):
                            continue
                        swap_indices = dict()
                        swap_tuples = self._mirror_value_swaps[key][layer_idx]
                        # Swaps.
                        for swappair in swap_tuples:
                            swap_indices[swappair[0]] = (
                                net.blobs[key].data[sample_idx, layer_idx] ==\
                                swappair[0])
                        for swappair in swap_tuples:
                            net.blobs[key].data[sample_idx, layer_idx][
                                swap_indices[swappair[0]]] = swappair[1]
                    if len(self._mirror_layer_swaps[key]) > 0:
                        new_layer_order = list(
                            range(net.blobs[key].data.shape[1]))
                        for swappair in self._mirror_layer_swaps[key]:
                            new_layer_order[swappair[0]],\
                                new_layer_order[swappair[1]] = \
                                    new_layer_order[swappair[1]],\
                                    new_layer_order[swappair[0]]
                        net.blobs[key].data[...] = net.blobs[key].data[
                            :, tuple(new_layer_order)]


# Is covered in example.py, which is run in a subprocess and not detected by
# coverage.py.
# pylint: disable=R0903
class _LossIndicator(object):  # pragma: no cover

    r"""
    A plugin indicator for the ``progressbar`` package.

    This must be used in conjunction with the
    :py:class:`barrista.monitoring.ProgressIndicator`. If available, it
    outputs current loss, accuracy, test loss and test accuracy.

    :param progress_indicator:
      :py:class:`barrista.monitoring.ProgressIndicator`. The information
      source to use.
    """

    def __init__(self, progress_indicator):
        self.progress_indicator = progress_indicator

    def __call__(self, pbar, stats):
        r"""Compatibility with new versions of ``progressbar2``."""
        return self.update(pbar)

    def update(self, pbar):  # pylint: disable=W0613
        """The update method to implement by the ``progressbar`` interface."""
        if self.progress_indicator.loss is not None:
            ret_val = 'Loss: {0:.4f}'.format(self.progress_indicator.loss)
        else:
            ret_val = 'Loss: -----'
        if self.progress_indicator.accuracy is not None:
            ret_val += '|Accy: {0:.4f}'.format(
                self.progress_indicator.accuracy)
        if self.progress_indicator.test_loss is not None:
            ret_val += '|TLoss: {0:.4f}'.format(
                self.progress_indicator.test_loss)
        if self.progress_indicator.test_accuracy is not None:
            ret_val += '|TAccy: {0:.4f}'.format(
                self.progress_indicator.test_accuracy)
        return ret_val


# Is covered in example.py, which is run in a subprocess and not detected by
# coverage.py.
# pylint: disable=R0903
class _SpeedIndicator(object):  # pragma: no cover

    r"""
    A plugin indicator for the ``progressbar`` package.

    :param progress_indicator:
      :py:class:`barrista.monitoring.ProgressIndicator`. The information
      source to use.
    """

    def __init__(self, progress_indicator):
        self._progress_indicator = progress_indicator
        self._active = True
        self._last_ret = None

    def __call__(self, pbar, stats):
        r"""Compatibility with new versions of ``progressbar2``."""
        return self.update(pbar)

    def update(self, pbar):  # pylint: disable=W0613
        """The update method to implement by the ``progressbar`` interface."""
        if not self._active:
            if self._last_ret is not None:
                return self._last_ret
            else:
                return ''
        # pylint: disable=protected-access
        ret_val = '|%.2f smpl./s' % (self._progress_indicator._smplps)
        self._last_ret = ret_val
        return ret_val


class ResultExtractor(Monitor):  # pylint: disable=R0903

    r"""
    This monitor is designed for monitoring scalar layer results.

    The main use case are salar outputs such as loss and accuracy.

    IMPORTANT: this monitor will change cbparams and add new values to it,
    most likely other monitors will depend on this, thus, ResultExtractors
    should be among the first monitors in the callback list, e.g. by
    insert them always in the beginning.

    It will extract the value of a layer and add the value to the cbparam.

    :param cbparam_key: string.
      The key we will overwrite/set in the cbparams dict.

    :param layer_name: string.
      The layer to extract the value from.
    """

    def __init__(self, cbparam_key, layer_name):
        """See class documentation."""
        self._layer_name = layer_name
        self._cbparam_key = cbparam_key
        self._init = False
        self._not_layer_available = True
        self._test_data = None

    def __call__(self, kwargs):
        """Callback implementation."""
        if self._not_layer_available and self._init:
            return
        Monitor.__call__(self, kwargs)

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):
        if self._init:
            raise Exception("This ResultExtractor is already initialized! "
                            "Did you try to use it for train and test?")
        if 'test' in kwargs['callback_signal']:
            tmp_net = kwargs['testnet']
        else:
            tmp_net = kwargs['net']
        if self._layer_name in list(tmp_net.blobs.keys()):
            self._not_layer_available = False
        self._init = True
        assert self._cbparam_key not in kwargs, (
            'it is only allowed to add keys to the cbparam,',
            'not overwrite them {} {}'.format(self._cbparam_key,
                                              list(kwargs.keys())))

    def _pre_train_batch(self, kwargs):
        kwargs[self._cbparam_key] = 0.0

    def _post_train_batch(self, kwargs):
        kwargs[self._cbparam_key] = float(
            kwargs['net'].blobs[self._layer_name].data[...].ravel()[0])

    def _pre_test(self, kwargs):
        self._test_data = []

    def _post_test(self, kwargs):
        kwargs[self._cbparam_key] = _np.mean(self._test_data)

    def _post_test_batch(self, kwargs):
        # need to multiply by batch_size since it is normalized
        # internally
        self._test_data.append(float(
            kwargs['testnet'].blobs[self._layer_name].data[...].ravel()[0]))
        kwargs[self._cbparam_key] = self._test_data[-1]


# Again, tested in a subprocess and not discovered.
# pylint: disable=R0903
class ProgressIndicator(Monitor):  # pragma: no cover

    r"""
    Generates a progress bar with current information about the process.

    The progress bar always displays completion percentage and ETA. If
    available, it also displays loss, accuracy, test loss and test accuracy.

    It makes use of the following keyword arguments (\* indicates required):

    * ``iter``\*,
    * ``max_iter``\*,
    * ``train_loss``,
    * ``test_loss``,
    * ``train_accuracy``,
    * ``test_accuracy``.
    """

    def __init__(self):
        """See class documentation."""
        self.loss = None
        self.test_loss = None
        self.accuracy = None
        self.test_accuracy = None
        from progressbar import ETA, Percentage, Bar, ProgressBar
        self.widgets = [Bar(), Percentage(), ' ', ETA()]
        self.pbarclass = ProgressBar
        self.pbar = None
        self._speed_indicator = None
        self._last_update = _time.time()
        self._smplps = 0

    def _post_train_batch(self, kwargs):
        if self.pbar is None:
            self._speed_indicator = _SpeedIndicator(self)
            if 'train_loss' in list(kwargs.keys()):
                widgets = [_LossIndicator(self),
                           self._speed_indicator] + self.widgets
            else:
                widgets = [self._speed_indicator] + self.widgets
            self.pbar = self.pbarclass(maxval=kwargs['max_iter'],
                                       widgets=widgets)
            self.pbar.start()
        if 'train_loss' in list(kwargs.keys()):
            self.loss = kwargs['train_loss']
        if 'train_accuracy' in list(kwargs.keys()):
            self.accuracy = kwargs['train_accuracy']
        self._smplps = float(kwargs['batch_size']) / (
            _time.time() - self._last_update)
        self._last_update = _time.time()
        self.pbar.update(value=kwargs['iter'])

    def _post_test_batch(self, kwargs):
        if self.pbar is None:
            self._speed_indicator = _SpeedIndicator(self)
            if 'test_loss' in list(kwargs.keys()):
                widgets = [_LossIndicator(self),
                           self._speed_indicator] + self.widgets
            else:
                widgets = [self._speed_indicator] + self.widgets
            self.pbar = self.pbarclass(maxval=kwargs['max_iter'],
                                       widgets=widgets)
            self.pbar.start()
        if 'test_loss' in list(kwargs.keys()):
            self.test_loss = kwargs['test_loss']
        if 'test_accuracy' in list(kwargs.keys()):
            self.test_accuracy = kwargs['test_accuracy']
        self._smplps = float(kwargs['batch_size']) / (
            _time.time() - self._last_update)
        self._last_update = _time.time()
        self.pbar.update(value=kwargs['iter'])

    def _post_test(self, kwargs):
        # Write the mean if possible.
        if self.pbar is not None:
            if 'test_loss' in list(kwargs.keys()):
                self.test_loss = kwargs['test_loss']
            if 'test_accuracy' in list(kwargs.keys()):
                self.test_accuracy = kwargs['test_accuracy']
            self.pbar.update(value=kwargs['iter'])

    def finalize(self, kwargs):  # pylint: disable=W0613
        """Call ``progressbar.finish()``."""
        if self._speed_indicator is not None:
            # pylint: disable=protected-access
            self._speed_indicator._active = False
        if self.pbar is not None:
            self.pbar.finish()


def _sorted_ar_from_dict(inf, key):  # pragma: no cover
    iters = []
    vals = []
    for values in inf:
        if values.has_key(key):
            iters.append(int(values['NumIters']))
            vals.append(float(values[key]))
    sortperm = _np.argsort(iters)
    arr = _np.array([iters, vals]).T
    return arr[sortperm, :]


def _draw_perfplot(phases, categories, ars, outfile):  # pragma: no cover
    """Draw the performance plots."""
    fig, axes = _plt.subplots(nrows=len(categories), sharex=True)
    for category_idx, category in enumerate(categories):
        ax = axes[category_idx]  # pylint: disable=invalid-name
        ax.set_title(category.title())
        for phase in phases:
            if phase + '_' + category not in ars.keys():
                continue
            ar = ars[phase + '_' + category]  # pylint: disable=invalid-name
            alpha = 0.7
            color = 'b'
            if phase == 'test':
                alpha = 1.0
                color = 'g'
            ax.plot(ar[:, 0], ar[:, 1],
                    label=phase.title(), c=color, alpha=alpha)
            if phase == 'test':
                ax.scatter(ar[:, 0], ar[:, 1],
                           c=color, s=50)
        ax.set_ylabel(category.title())
        ax.grid()
        ax.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    _plt.savefig(outfile, bbox_inches='tight')
    _plt.close(fig)


class JSONLogger(Monitor):  # pylint: disable=R0903

    r"""
    Logs available information to a JSON file.

    The information is stored in a dictionary of lists. The lists contain
    score information and the iteration at which it was obtained. The
    currently logged scores are loss, accuracy, test loss and test accuracy.

    The logger makes use of the following keyword arguments
    (\* indicates required):

    * ``iter``\*,

    :param path: string.
      The path to store the file in.

    :param name: string.
      The filename. Will be prefixed with 'barrista_' and '.json' will be
      appended.

    :param logging: dict of lists.
      The two keys in the dict which are used are test, train.
      For each of those a list of keys can be provided, those keys
      have to be available in the kwargs/cbparams structure.
      Usually the required data is provided by the ResultExtractor.

    :param base_iter: int or None.
      If provided, add this value to the number of iterations. This overrides
      the number of iterations retrieved from a loaded JSON log to append to.

    :param write_every: int or None.
      Write the JSON log every `write_every` iterations. The log is always
      written upon completion of the training. If it is None, the log is only
      written on completion.

    :param create_plot: bool.
      If set to True, create a plot at `path` when the JSON log is written with
      the name of the JSON file + `_plot.png`. Default: False.
    """
    # pylint: disable=too-many-arguments
    def __init__(self,
                 path,
                 name,
                 logging,
                 base_iter=None,
                 write_every=None,
                 create_plot=False):
        """See class documentation."""
        import json
        self.json_package = json
        self.json_filename = str(_os.path.join(
            path,
            'barrista_' + name + '.json'))
        if base_iter is None:
            self.base_iter = 0
        else:
            self.base_iter = base_iter
        if _os.path.exists(self.json_filename):
            with open(self.json_filename, 'r') as infile:
                self.dict = self.json_package.load(infile)
            if base_iter is None:
                for key in ['train', 'test']:
                    for infdict in self.dict[key]:
                        if infdict.has_key('NumIters'):
                            self.base_iter = max(self.base_iter,
                                                 infdict['NumIters'])
            _LOGGER.info("Appending to JSON log at %s from iteration %d.",
                         self.json_filename,
                         self.base_iter)
        else:
            self.dict = {'train': [], 'test': [], 'barrista_produced': True}
        assert write_every is None or write_every > 0
        self._write_every = write_every
        self._logging = logging
        self._create_plot = create_plot
        if self._create_plot:
            assert _PLT_AVAILABLE, (
                "Matplotlib must be available to use plotting!")

    def _initialize_train(self, kwargs):
        self._initialize(kwargs)

    def _initialize_test(self, kwargs):
        self._initialize(kwargs)

    def _initialize(self, kwargs):  # pylint: disable=unused-argument
        for key in list(self._logging.keys()):
            assert key in ['train', 'test'], (
                'only train and test is supported by this logger')

    def _post_test(self, kwargs):
        self._post('test', kwargs)

    def _post_train_batch(self, kwargs):
        self._post('train', kwargs)

    def _post(self, phase_name, kwargs):  # pylint: disable=C0111
        if phase_name not in self._logging:  # pragma: no cover
            return
        if phase_name == 'train':
            kwargs['iter'] += kwargs['batch_size']
            if (self._write_every is not None and
                    kwargs['iter'] % self._write_every == 0):
                with open(self.json_filename, 'w') as outf:
                    self.json_package.dump(self.dict, outf)
                if self._create_plot:  # pragma: no cover
                    categories = set()
                    arrs = dict()
                    for plot_phase_name in ['train', 'test']:
                        for key in self._logging[plot_phase_name]:
                            categories.add(key[len(plot_phase_name) + 1:])
                            arrs[key] = _sorted_ar_from_dict(self.dict[plot_phase_name],
                                                             key)
                    _draw_perfplot(['train', 'test'],
                                   categories,
                                   arrs,
                                   self.json_filename + '_plot.png')
        for key in self._logging[phase_name]:
            if key in kwargs:
                self.dict[phase_name].append({'NumIters':
                                              kwargs['iter'] + self.base_iter,
                                              key: kwargs[key]})
        if phase_name == 'train':
            kwargs['iter'] -= kwargs['batch_size']

    def finalize(self, kwargs):  # pylint: disable=W0613
        """Write the json file."""
        with open(self.json_filename, 'w') as outf:
            self.json_package.dump(self.dict, outf)
        if self._create_plot:  # pragma: no cover
            categories = set()
            arrs = dict()
            for phase_name in ['train', 'test']:
                for key in self._logging[phase_name]:
                    categories.add(key[len(phase_name) + 1:])
                    arrs[key] = _sorted_ar_from_dict(self.dict[phase_name], key)
            _draw_perfplot(['train', 'test'],
                           categories,
                           arrs,
                           self.json_filename + '_plot.png')



class Checkpointer(Monitor):  # pylint: disable=R0903

    r"""
    Writes the network blobs to disk at certain iteration intervals.

    The logger makes use of the following keyword arguments
    (\* indicates required):

    * ``iter``\*,
    * ``net``\*,
    * ``batch_size``\*.

    :param name_prefix: string or None.
      The first part of the output filenames to generate. The prefix '_iter_,
      the current iteration, as well as '.caffemodel' is added.

      If you are using a caffe version from later than Dec. 2015, caffe's
      internal snapshot method is exposed to Python and also snapshots the
      solver. If it's available, then this method will be used. However,
      in that case, it's not possible to influence the storage location
      from Python. Please use the solver parameter ``snapshot_prefix``
      when constructing the solver instead (this parameter may be None
      and is unused then).

    :param iterations: int > 0.
      Always if the current number of iterations is divisible by iterations,
      the network blobs are written to disk. Hence, this value must be a
      multiple of the batch size!
    """

    def __init__(self,
                 name_prefix,
                 iterations,
                 base_iterations=0):
        """See class documentation."""
        assert iterations > 0
        _LOGGER.info('Setting up checkpointing with name prefix %s every ' +
                     '%d iterations.', name_prefix, iterations)
        self.name_prefix = name_prefix
        self.iterations = iterations
        self.created_checkpoints = []
        self._base_iterations = base_iterations

    # pylint: disable=arguments-differ
    def _post_train_batch(self, kwargs, finalize=False):
        assert self.iterations % kwargs['batch_size'] == 0, (
            'iterations not multiple of batch_size, {} vs {}'.format(
                self.iterations, kwargs['batch_size']))
        # Prevent double-saving.
        if kwargs['iter'] in self.created_checkpoints:
            return
        if ((kwargs['iter'] + self._base_iterations +
             kwargs['batch_size']) % self.iterations == 0 or
                finalize):
            self.created_checkpoints.append(kwargs['iter'])
            # pylint: disable=protected-access
            if not hasattr(kwargs['solver']._solver, 'snapshot'):  # pragma: no cover
                checkpoint_filename = (
                    self.name_prefix + '_iter_' +
                    str(int((kwargs['iter'] + self._base_iterations) /
                            kwargs['batch_size']) + 1) +
                    '.caffemodel')
                _LOGGER.debug("Writing checkpoint to file '%s'.",
                              checkpoint_filename)
                kwargs['net'].save(checkpoint_filename)
            else:
                # pylint: disable=protected-access
                kwargs['solver']._solver.snapshot()
                caffe_checkpoint_filename = (self.name_prefix +
                                             '_iter_' +
                                             str((kwargs['iter'] + self._base_iterations) /
                                                 kwargs['batch_size'] + 1) +
                                             '.caffemodel')
                caffe_sstate_filename = (self.name_prefix +
                                         '_iter_' +
                                         str((kwargs['iter'] + self._base_iterations) /
                                             kwargs['batch_size'] + 1) +
                                         '.solverstate')
                _LOGGER.debug('Writing checkpoint to file "[solverprefix]%s" ' +
                              'and "[solverprefix]%s".',
                              caffe_checkpoint_filename,
                              caffe_sstate_filename)
                assert _os.path.exists(caffe_checkpoint_filename), (
                    "An error occured checkpointing to {}. File not found. "
                    "Make sure the `base_iterations` and the `name_prefix` "
                    "are correct.").format(caffe_checkpoint_filename)
                assert _os.path.exists(caffe_sstate_filename), (
                    "An error occured checkpointing to {}. File not found. "
                    "Make sure the `base_iterations` and the `name_prefix` "
                    "are correct.").format(caffe_sstate_filename)

    def finalize(self, kwargs):
        """Write a final checkpoint."""
        # Account for the counting on iteration increase for the last batch.
        kwargs['iter'] -= kwargs['batch_size']
        self._post_train_batch(kwargs, finalize=True)
        kwargs['iter'] += kwargs['batch_size']


class GradientMonitor(Monitor):

    """
    Tools to keep an eye on the gradient.

    Create plots of the gradient. Creates histograms of the gradient for all
    ``selected_parameters`` and creates an overview plot with the maximum
    absolute gradient per layer. If ``create_videos`` is set and ffmpeg is
    available, automatically creates videos.

    :param write_every: int.
      Write every x iterations. Since matplotlib takes some time to run, choose
      with care.

    :param output_folder: string.
      Where to store the outputs.

    :param selected_parameters: dict(string, list(int)) or None.
      Which parameters to include in the plots. The string is the name of the
      layer, the list of integers contains the parts to include, e.g., for a
      convolution layer, specify the name of the layer as key and 0 for
      the parameters of the convolution weights, 1 for the biases per channel.
      The order and meaning of parameter blobs is determined by caffe. If
      None, then all parameters are plotted. Default: None.

    :param relative: Bool.
      If set to True, will give the weights relative to the max absolute weight
      in the target parameter blob. Default: False.

    :param iteroffset: int.
      An iteration offset if training is resumed to not overwrite existing
      output. Default: 0.

    :param create_videos: Bool.
      If set to True, try to create a video using ffmpeg. Default: True.

    :param video_frame_rate: int.
      The video frame rate.
    """

    def __init__(self,  # pylint: disable=too-many-arguments
                 write_every,
                 output_folder,
                 selected_parameters=None,
                 relative=False,
                 iteroffset=0,
                 create_videos=True,
                 video_frame_rate=1):
        assert write_every > 0
        self._write_every = write_every
        self._output_folder = output_folder
        self._selected_parameters = selected_parameters
        self._relative = relative
        self._n_parameters = None
        self._iteroffset = iteroffset
        self._create_videos = create_videos
        self._video_frame_rate = video_frame_rate

    def _initialize_train(self, kwargs):  # pragma: no cover
        assert _PLT_AVAILABLE, (
            "Matplotlib must be available to use the GradientMonitor!")
        assert self._write_every % kwargs['batch_size'] == 0, (
            "`write_every` must be a multiple of the batch size!")
        self._n_parameters = 0
        if self._selected_parameters is not None:
            for name in self._selected_parameters.keys():
                assert name in kwargs['net'].params.keys()
                for p_idx in self._selected_parameters[name]:
                    assert p_idx >= 0
                    assert len(kwargs['net'].params[name]) > p_idx
                    self._n_parameters += 1
        else:
            self._selected_parameters = _collections.OrderedDict()
            for name in kwargs['net'].params.keys():
                self._selected_parameters[name] = range(len(
                    kwargs['net'].params[name]))
                self._n_parameters += len(kwargs['net'].params[name])

    # pylint: disable=too-many-locals
    def _post_train_batch(self, kwargs):  # pragma: no cover
        if kwargs['iter'] % self._write_every == 0:
            net = kwargs['net']
            maxabsupdates = {}
            maxabsupdates_flat = []
            # Create histograms.
            fig, axes = _plt.subplots(nrows=1,
                                      ncols=self._n_parameters,
                                      figsize=(self._n_parameters * 3, 3))
            ax_idx = 0
            xfmt = _tkr.FormatStrFormatter('%.1e')
            for lname in self._selected_parameters.keys():
                maxabsupdates[lname] = []
                for p_idx in self._selected_parameters[lname]:
                    if self._relative:
                        lgradient = (net.params[lname][p_idx].diff /
                                     net.params[lname][p_idx].data.max())
                    else:
                        lgradient = net.params[lname][p_idx].diff
                    maxabsupdates[lname].append(_np.max(_np.abs(lgradient)))
                    maxabsupdates_flat.append(_np.max(_np.abs(lgradient)))
                    axes[ax_idx].set_title(lname + ', p%d' % (p_idx))
                    axes[ax_idx].hist(list(lgradient.flat),
                                      25,
                                      normed=1,
                                      alpha=0.5)
                    axes[ax_idx].set_xticks(_np.linspace(-maxabsupdates_flat[-1],
                                                         maxabsupdates_flat[-1],
                                                         num=3))
                    axes[ax_idx].yaxis.set_visible(False)
                    axes[ax_idx].xaxis.set_major_formatter(xfmt)
                    ax_idx += 1
            _plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            _plt.suptitle("Gradient histograms for iteration %d" % (
                kwargs['iter'] + self._iteroffset))
            if self._relative:
                ghname = self._output_folder + 'gradient_hists_rel_%d.png' % (
                    (self._iteroffset + kwargs['iter']) /
                    self._write_every)
            else:
                ghname = self._output_folder + 'gradient_hists_%d.png' % (
                    (self._iteroffset + kwargs['iter']) /
                    self._write_every)
            _plt.savefig(ghname)
            _plt.close(fig)
            # Create the magnitude overview plot.
            fig = _plt.figure(figsize=(self._n_parameters * 1, 1.5))
            _plt.title("Maximum absolute gradient per layer (iteration %d)" % (
                kwargs['iter'] + self._iteroffset))
            ax = _plt.gca()  # pylint: disable=invalid-name
            # pylint: disable=invalid-name
            im = ax.imshow(_np.atleast_2d(_np.array(maxabsupdates_flat)),
                           interpolation='none')
            ax.yaxis.set_visible(False)
            divider = _make_axes_locatable(ax)
            cax = divider.append_axes("right", size="10%", pad=0.05)
            _plt.colorbar(im, cax=cax, ticks=_np.linspace(_np.min(maxabsupdates_flat),
                                                          _np.max(maxabsupdates_flat),
                                                          5))
            _plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            if self._relative:
                gmname = self._output_folder + 'gradient_magnitude_rel_%d.png' % (
                    (self._iteroffset + kwargs['iter']) /
                    self._write_every)
            else:
                gmname = self._output_folder + 'gradient_magnitude_%d.png' % (
                    (self._iteroffset + kwargs['iter']) /
                    self._write_every)
            _plt.savefig(gmname)
            _plt.close(fig)

    def finalize(self, kwargs):  # pragma: no cover
        if self._create_videos:
            _LOGGER.debug("Creating gradient videos...")
            try:
                if not _os.path.exists(_os.path.join(self._output_folder,
                                                     'videos')):
                    _os.mkdir(_os.path.join(self._output_folder, 'videos'))
                if self._relative:
                    rel_add = '_rel'
                else:
                    rel_add = ''
                with open(_os.devnull, 'w') as quiet:
                    _subprocess.check_call([
                        'ffmpeg',
                        '-y',
                        '-start_number', str(0),
                        '-r', str(self._video_frame_rate),
                        '-i', _os.path.join(self._output_folder,
                                            'gradient_hists' + rel_add + '_%d.png'),
                        _os.path.join(self._output_folder,
                                      'videos',
                                      'gradient_hists' + rel_add + '.mp4')
                    ], stdout=quiet, stderr=quiet)
                    _subprocess.check_call([
                        'ffmpeg',
                        '-y',
                        '-start_number', str(0),
                        '-r', str(self._video_frame_rate),
                        '-i', _os.path.join(self._output_folder,
                                            'gradient_magnitude' + rel_add + '_%d.png'),
                        _os.path.join(self._output_folder,
                                      'videos',
                                      'gradient_magnitude' + rel_add + '.mp4')
                    ], stdout=quiet, stderr=quiet)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Could not create videos! Error: %s. Is " +
                    "ffmpeg available on the command line?",
                    str(ex))
            _LOGGER.debug("Done.")


class ActivationMonitor(Monitor):

    """
    Tools to keep an eye on the net activations.

    Create plots of the net activations. If ``create_videos`` is set and
    ffmpeg is available, automatically creates videos.

    :param write_every: int.
      Write every x iterations. Since matplotlib takes some time to run, choose
      with care.

    :param output_folder: string.
      Where to store the outputs.

    :param selected_blobs: list(string) or None.
      Which blobs to include in the plots. If
      None, then all parameters are plotted. Default: None.

    :param iteroffset: int.
      An iteration offset if training is resumed to not overwrite existing
      output. Default: 0.

    :param sample: dict(string, NDarray(3D)).
      A sample to use that will be forward propagated to obtain the activations.
      Must contain one for every input layer of the network. Each sample is not
      preprocessed and must fit the input. If None, use the existing values
      from the blobs.

    :param create_videos: Bool.
      If set to True, try to create a video using ffmpeg. Default: True.

    :param video_frame_rate: int.
      The video frame rate.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,  # pragma: no cover
                 write_every,
                 output_folder,
                 selected_blobs=None,
                 iteroffset=0,
                 sample=None,
                 create_videos=True,
                 video_frame_rate=1):
        assert write_every > 0
        self._write_every = write_every
        self._output_folder = output_folder
        self._selected_blobs = selected_blobs
        self._n_parameters = None
        self._iteroffset = iteroffset
        self._create_videos = create_videos
        self._video_frame_rate = video_frame_rate
        self._sample = sample

    def _initialize_train(self, kwargs):  # pragma: no cover
        assert _PLT_AVAILABLE, (
            "Matplotlib must be available to use the ActivationMonitor!")
        assert self._write_every % kwargs['batch_size'] == 0, (
            "`write_every` must be a multiple of the batch size!")
        self._n_parameters = 0
        if self._selected_blobs is not None:
            for name in self._selected_blobs:
                assert name in kwargs['net'].blobs.keys(), (
                    "The activation monitor should monitor {}, which is not "
                    "part of the net!").format(name)
                self._n_parameters += 1
        else:
            self._selected_blobs = []
            for name in kwargs['net'].blobs.keys():
                bshape = kwargs['net'].blobs[name].data.shape
                if len(bshape) == 4:
                    self._selected_blobs.append(name)
                    self._n_parameters += 1
        if self._sample is not None:
            for inp_name in self._sample.keys():
                assert (kwargs['net'].blobs[inp_name].data.shape[1:] ==
                        self._sample[inp_name].shape), (
                            "All provided inputs as `sample` must have the shape "
                            "of an input blob, starting from its sample "
                            "dimension. Does not match for %s: %s vs. %s." % (
                                inp_name,
                                str(kwargs['net'].blobs[inp_name].data.shape[1:]),
                                str(self._sample[inp_name].shape)))

    # pylint: disable=too-many-locals
    def _post_train_batch(self, kwargs):  # pragma: no cover
        if kwargs['iter'] % self._write_every == 0:
            net = kwargs['net']
            if self._sample is not None:
                for bname in self._sample.keys():
                    net.blobs[bname].data[-1, ...] = self._sample[bname]
                    net.forward()
            for bname in self._selected_blobs:
                blob = net.blobs[bname].data
                nchannels = blob.shape[1]
                gridlen = int(_np.ceil(_np.sqrt(nchannels)))
                fig, axes = _plt.subplots(nrows=gridlen,
                                          ncols=gridlen,
                                          squeeze=False)
                bmin = blob[-1].min()
                bmax = blob[-1].max()
                for c_idx in range(nchannels):
                    ax = axes.flat[c_idx]  # pylint: disable=invalid-name
                    im = ax.imshow(blob[-1, c_idx],  # pylint: disable=invalid-name
                                   vmin=bmin,
                                   vmax=bmax,
                                   cmap='Greys_r',
                                   interpolation='none')
                    ax.set_title('C%d' % (c_idx))
                    ax.yaxis.set_visible(False)
                    ax.xaxis.set_visible(False)
                # pylint: disable=undefined-loop-variable
                for blank_idx in range(c_idx + 1, gridlen * gridlen):
                    ax = axes.flat[blank_idx]  # pylint: disable=invalid-name
                    ax.axis('off')
                _plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                _plt.suptitle("Activations in blob %s (iteration %d)" % (
                    bname, self._iteroffset + kwargs['iter']))
                cbax, cbkw = _colorbar.make_axes([ax for ax in axes.flat])
                fig.colorbar(im, cax=cbax, **cbkw)
                _plt.savefig(self._output_folder +
                             'activations_%s_%d.png' % (
                                 bname,
                                 (self._iteroffset + kwargs['iter']) /
                                 self._write_every))
                _plt.close(fig)

    def finalize(self, kwargs):  # pragma: no cover
        if self._create_videos:
            _LOGGER.debug("Creating activation videos...")
            try:
                if not _os.path.exists(_os.path.join(self._output_folder,
                                                     'videos')):
                    _os.mkdir(_os.path.join(self._output_folder, 'videos'))
                for bname in self._selected_blobs:
                    with open(_os.devnull, 'w') as quiet:
                        _subprocess.check_call([
                            'ffmpeg',
                            '-y',
                            '-start_number', str(0),
                            '-r', str(self._video_frame_rate),
                            '-i', _os.path.join(self._output_folder,
                                                'activations_' + bname + '_%d.png'),
                            _os.path.join(self._output_folder,
                                          'videos',
                                          'activations_' + bname + '.mp4')
                        ], stdout=quiet, stderr=quiet)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Could not create videos! Error: %s. Is " +
                    "ffmpeg available on the command line?",
                    str(ex))
            _LOGGER.debug("Done.")


class FilterMonitor(Monitor):

    """
    Tools to keep an eye on the filters.

    Create plots of the network filters. Creates filter plots for all
    ``selected_parameters``. If ``create_videos`` is set and ffmpeg is
    available, automatically creates videos.

    :param write_every: int.
      Write every x iterations. Since matplotlib takes some time to run, choose
      with care.

    :param output_folder: string.
      Where to store the outputs.

    :param selected_parameters: dict(string, list(int)) or None.
      Which parameters to include in the plots. The string is the name of the
      layer, the list of integers contains the parts to include, e.g., for a
      convolution layer, specify the name of the layer as key and 0 for
      the parameters of the convolution weights, 1 for the biases per channel.
      The order and meaning of parameter blobs is determined by caffe. If
      None, then all parameters are plotted. **Only 4D blobs can be plotted!**
      Default: None.

    :param iteroffset: int.
      An iteration offset if training is resumed to not overwrite existing
      output. Default: 0.

    :param create_videos: Bool.
      If set to True, try to create a video using ffmpeg. Default: True.

    :param video_frame_rate: int.
      The video frame rate.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,  # pragma: no cover
                 write_every,
                 output_folder,
                 selected_parameters=None,
                 iteroffset=0,
                 create_videos=True,
                 video_frame_rate=1):
        assert write_every > 0
        self._write_every = write_every
        self._output_folder = output_folder
        self._selected_parameters = selected_parameters
        self._n_parameters = None
        self._iteroffset = iteroffset
        self._create_videos = create_videos
        self._video_frame_rate = video_frame_rate

    def _initialize_train(self, kwargs):  # pragma: no cover
        assert _PLT_AVAILABLE, (
            "Matplotlib must be available to use the FilterMonitor!")
        assert self._write_every % kwargs['batch_size'] == 0, (
            "`write_every` must be a multiple of the batch size!")
        self._n_parameters = 0
        if self._selected_parameters is not None:
            for name in self._selected_parameters.keys():
                assert name in kwargs['net'].params.keys()
                for p_idx in self._selected_parameters[name]:
                    assert p_idx >= 0
                    assert len(kwargs['net'].params[name][p_idx].data.shape) == 4
                    self._n_parameters += 1
        else:
            self._selected_parameters = _collections.OrderedDict()
            for name in kwargs['net'].params.keys():
                self._selected_parameters[name] = []
                for pindex in range(len(kwargs['net'].params[name])):
                    if len(kwargs['net'].params[name][pindex].data.shape) == 4:
                        self._selected_parameters[name].append(pindex)
                        self._n_parameters += 1

    def _post_train_batch(self, kwargs):  # pragma: no cover
        if kwargs['iter'] % self._write_every == 0:
            net = kwargs['net']
            for pname in self._selected_parameters.keys():
                for pindex in self._selected_parameters[pname]:
                    fig = _plt.figure()
                    param = net.params[pname][pindex].data
                    border = 2
                    collected_weights = _np.zeros((param.shape[0] *
                                                   (param.shape[2] + border) +
                                                   border,
                                                   param.shape[1] *
                                                   (param.shape[3] + border) +
                                                   border), dtype='float32')
                    pmin = param.min()
                    pmax = param.max()
                    # Build up the plot manually because matplotlib is too slow.
                    for filter_idx in range(param.shape[0]):
                        for layer_idx in range(param.shape[1]):
                            collected_weights[border + filter_idx * (param.shape[2] + border):
                                              border + filter_idx * (param.shape[2] + border) +
                                              param.shape[2],
                                              border + layer_idx * (param.shape[3] + border):
                                              border + layer_idx * (param.shape[3] + border) +
                                              param.shape[3]] = (
                                                  (param[filter_idx, layer_idx] - pmin)
                                                  / (pmax - pmin))
                    _plt.imshow(collected_weights,
                                cmap='Greys_r',
                                interpolation='none')
                    ax = _plt.gca()  # pylint: disable=invalid-name
                    ax.yaxis.set_visible(False)
                    ax.xaxis.set_visible(False)
                    ax.set_title((
                        "Values of layer %s, param %d\n" +
                        "(iteration %d, min %.1e, max %.1e)") % (
                            pname, pindex, self._iteroffset + kwargs['iter'], pmin, pmax))
                    _plt.savefig(self._output_folder +
                                 'parameters_%s_%d_%d.png' % (
                                     pname,
                                     pindex,
                                     (self._iteroffset + kwargs['iter']) /
                                     self._write_every))
                    _plt.close(fig)

    def finalize(self, kwargs):  # pragma: no cover
        if self._create_videos:
            _LOGGER.debug("Creating filter videos...")
            try:
                if not _os.path.exists(_os.path.join(self._output_folder,
                                                     'videos')):
                    _os.mkdir(_os.path.join(self._output_folder, 'videos'))
                for pname in self._selected_parameters.keys():
                    for pindex in self._selected_parameters[pname]:
                        with open(_os.devnull, 'w') as quiet:
                            _subprocess.check_call([
                                'ffmpeg',
                                '-y',
                                '-start_number', str(0),
                                '-r', str(self._video_frame_rate),
                                '-i', _os.path.join(self._output_folder,
                                                    'parameters_' +
                                                    pname + '_' +
                                                    str(pindex) + '_' +
                                                    '%d.png'),
                                _os.path.join(self._output_folder,
                                              'videos',
                                              'parameters_' +
                                              pname + '_' +
                                              str(pindex) + '.mp4')
                            ], stdout=quiet, stderr=quiet)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Could not create videos! Error: %s. Is " +
                    "ffmpeg available on the command line?",
                    str(ex))
            _LOGGER.debug("Done.")
