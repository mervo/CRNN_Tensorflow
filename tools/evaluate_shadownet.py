#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 17-9-25 下午3:56
# @Author  : Luo Yao
# @Site    : http://github.com/TJCVRS
# @File    : test_shadownet.py
# @IDE: PyCharm Community Edition
"""
Test shadow net script
"""
import argparse
import os.path as ops
import math

import tensorflow as tf
import matplotlib.pyplot as plt
import numpy as np
import glog as log

from crnn_model import crnn_model
from config import global_config
from data_provider import shadownet_data_feed_pipline
from data_provider import tf_io_pipline_tools
from local_utils import evaluation_tools


CFG = global_config.cfg


def init_args():
    """
    :return: parsed arguments and (updated) config.cfg object
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset_dir', type=str,
                        help='Directory containing test_features.tfrecords')
    parser.add_argument('-c', '--char_dict_path', type=str,
                        help='Directory where character dictionaries for the dataset were stored')
    parser.add_argument('-o', '--ord_map_dict_path', type=str,
                        help='Directory where ord map dictionaries for the dataset were stored')
    parser.add_argument('-w', '--weights_path', type=str, required=True,
                        help='Path to pre-trained weights')
    parser.add_argument('-v', '--visualize', type=bool, default=False,
                        help='Whether to display images')

    return parser.parse_args()


def test_shadownet(dataset_dir, weights_path, char_dict_path,
                   ord_map_dict_path, is_visualize=True,
                   is_process_all_data=False):
    """

    :param dataset_dir:
    :param weights_path:
    :param char_dict_path:
    :param ord_map_dict_path:
    :param is_visualize:
    :param is_process_all_data:
    :return:
    """
    # prepare dataset
    test_dataset = shadownet_data_feed_pipline.CrnnDataFeeder(
        dataset_dir=dataset_dir,
        char_dict_path=char_dict_path,
        ord_map_dict_path=ord_map_dict_path,
        flags='train'
    )
    test_images, test_labels, test_images_paths = test_dataset.inputs(
        batch_size=CFG.TEST.BATCH_SIZE,
        num_epochs=1
    )

    # set up test sample count
    log.info('Start computing test dataset sample counts')
    if is_process_all_data:
        test_sample_count = test_dataset.sample_counts()
        num_iterations = int(math.ceil(test_sample_count / CFG.TEST.BATCH_SIZE))
    else:
        num_iterations = 1

    # declare crnn net
    shadownet = crnn_model.ShadowNet(
        phase='test',
        hidden_nums=CFG.ARCH.HIDDEN_UNITS,
        layers_nums=CFG.ARCH.HIDDEN_LAYERS,
        num_classes=CFG.ARCH.NUM_CLASSES
    )
    # set up decoder
    decoder = tf_io_pipline_tools.TextFeatureIO(
        char_dict_path=char_dict_path,
        ord_map_dict_path=ord_map_dict_path
    ).reader

    # compute inference result
    test_inference_ret = shadownet.inference(
        inputdata=test_images,
        name='shadow_net',
        reuse=False
    )
    test_decoded, test_log_prob = tf.nn.ctc_beam_search_decoder(
        test_inference_ret,
        CFG.ARCH.SEQ_LENGTH * np.ones(CFG.TEST.BATCH_SIZE),
        merge_repeated=False
    )

    # Set saver configuration
    saver = tf.train.Saver()

    # Set sess configuration
    sess_config = tf.ConfigProto(allow_soft_placement=True)
    sess_config.gpu_options.per_process_gpu_memory_fraction = CFG.TRAIN.GPU_MEMORY_FRACTION
    sess_config.gpu_options.allow_growth = CFG.TRAIN.TF_ALLOW_GROWTH

    sess = tf.Session(config=sess_config)

    with sess.as_default():
        saver.restore(sess=sess, save_path=weights_path)

        log.info('Start predicting...')

        accuracy = 0
        for epoch in range(num_iterations):
            test_predictions_value, test_images_value, test_labels_value, \
            test_images_paths_value = sess.run(
                [test_decoded, test_images, test_labels, test_images_paths]
            )
            test_images_paths_value = np.reshape(
                test_images_paths_value,
                newshape=test_images_paths_value.shape[0]
            )
            test_images_paths_value = [tmp.decode('utf-8') for tmp in test_images_paths_value]
            test_images_names_value = [ops.split(tmp)[0] for tmp in test_images_paths_value]
            test_labels_value = decoder.sparse_tensor_to_str(test_labels_value)
            test_predictions_value = decoder.sparse_tensor_to_str(test_predictions_value[0])

            accuracy += evaluation_tools.compute_accuracy(
                test_labels_value, test_predictions_value, display=False
            )

            for index, test_image in enumerate(test_images_value):
                print('Predict {:s} image with gt label: {:s} **** predicted label: {:s}'.format(
                    test_images_names_value[index], test_labels_value[index], test_predictions_value[index]))

                # avoid accidentally displaying for the whole dataset
                if is_visualize and not is_process_all_data:
                    plt.imshow(np.array(test_image, np.uint8)[:, :, (2, 1, 0)])
                    plt.show()

        # We compute a mean of means, so we need the sample sizes to be constant
        # (BATCH_SIZE) for this to equal the actual mean
        accuracy /= num_iterations
        log.info('Mean test accuracy is {:5f}'.format(accuracy))


if __name__ == '__main__':
    """
    test code
    """
    args = init_args()

    test_shadownet(
        dataset_dir=args.dataset_dir,
        weights_path=args.weights_path,
        char_dict_path=args.char_dict_path,
        ord_map_dict_path=args.ord_map_dict_path,
        is_visualize=args.visualize
    )