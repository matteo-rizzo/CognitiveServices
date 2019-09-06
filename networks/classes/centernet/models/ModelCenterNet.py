import glob
import os

import pandas as pd
from keras_preprocessing.image import ImageDataGenerator
from typing import Dict, List, Union

import numpy as np
import tensorflow as tf
from tensorflow.python.keras.callbacks import ModelCheckpoint, TensorBoard, LearningRateScheduler
# from networks.classes.centernet.models.ModelGenerator import ModelGenerator


from networks.classes.centernet.models.ModelGeneratorNew import ModelGenerator


class ModelCenterNet:

    def __init__(self, logs: Dict):
        self.__logs = logs

    def build_model(self, input_shape, mode: str, n_category: int = 1) -> tf.keras.Model:
        """
        Builds the network.

        :param input_shape: the shape of the input images
        :param mode: the type of model that must be generated
        :param n_category: the number of categories (possible classes). Defaults to 1 in order to detect the
        presence or absence of an object only (and not its label).
        :return: a Keras model
        """

        self.__logs['execution'].info('Building {} model...'.format(mode))

        return ModelGenerator().generate_model(input_shape, mode, n_category)

    @staticmethod
    def setup_callbacks(weights_log_path: str, batch_size: int, lr: float) -> List[tf.keras.callbacks.Callback]:
        """
        Sets up the callbacks for the training of the model.
        """

        # Setup callback to save the best weights after each epoch
        checkpointer = ModelCheckpoint(filepath=os.path.join(weights_log_path,
                                                             'weights.{epoch:02d}-{val_loss:.2f}.hdf5'),
                                       verbose=0,
                                       save_best_only=True,
                                       save_weights_only=True,
                                       monitor='val_loss',
                                       mode='min')

        tensorboard_log_dir = os.path.join(weights_log_path, 'tensorboard')

        # Note that update_freq is set to batch_size * 10,
        # because the epoch takes too long and batch size too short
        tensorboard = TensorBoard(log_dir=tensorboard_log_dir,
                                  write_graph=True,
                                  histogram_freq=0,
                                  write_grads=True,
                                  write_images=False,
                                  batch_size=batch_size,
                                  update_freq=batch_size * 10)

        # Setup early stopping to stop training if val_loss is not increasing after 3 epochs
        # early_stopping = EarlyStopping(
        #    monitor='val_loss',
        #    patience=2,
        #    mode='min',
        # )

        def lrs(epoch):
            lrate = lr
            if epoch > 20:
                lrate = lr / 10
            return lrate

        lr_schedule = LearningRateScheduler(lrs)

        return [tensorboard, checkpointer, lr_schedule]

    def restore_weights(self,
                        model: tf.keras.Model,
                        init_epoch: int,
                        weights_folder_path: str) -> None:
        """
        Restores the weights from an existing weights file

        :param model:
        :param init_epoch:
        :param weights_folder_path:
        """

        init_epoch_str = '0' + str(init_epoch) if init_epoch < 10 else str(init_epoch)

        restore_path_reg = os.path.join(weights_folder_path, 'weights.{}-*.hdf5'.format(init_epoch_str))
        list_files = glob.glob(restore_path_reg)
        assert len(list_files) > 0, \
            'ERR: No weights file match provided name {}'.format(restore_path_reg)

        # Take real filename
        restore_filename = list_files[0].split('/')[-1]
        restore_path = os.path.join(weights_folder_path, restore_filename)
        assert os.path.isfile(restore_path), \
            'ERR: Weight file in path {} seems not to be a file'.format(restore_path)

        self.__logs['execution'].info("Restoring weights in file {}...".format(restore_filename))
        model.load_weights(restore_path)

    def train(self,
              dataset: any,
              model: tf.keras.Model,
              init_epoch: int,
              epochs: int,
              batch_size: int,
              callbacks: List[tf.keras.callbacks.Callback],
              augmentation: bool = False):
        """
        Compiles and trains the model for the specified number of epochs.
        """

        self.__logs['training'].info('Training the model...\n')

        # Display the architecture of the model
        self.__logs['training'].info('Architecture of the model:')
        model.summary()

        # Train the model
        self.__logs['training'].info('Starting the fitting procedure:')
        self.__logs['training'].info('* Total number of epochs:   ' + str(epochs))
        self.__logs['training'].info('* Initial epoch:            ' + str(init_epoch) + '\n')

        training_set, training_set_size = dataset.get_training_set()
        validation_set, validation_set_size = dataset.get_validation_set()
        training_steps = training_set_size // batch_size + 1
        validation_steps = validation_set_size // batch_size + 1

        if augmentation:
            x, y = dataset.get_xy_training()

            image_data_generator = ImageDataGenerator(brightness_range=[0.2, 1.0],
                                                      rotation_range=10,
                                                      width_shift_range=0.1,
                                                      height_shift_range=0.1,
                                                      zoom_range=.1)

            generator = image_data_generator.flow_from_dataframe(
                dataframe=pd.DataFrame({'image': x, 'class': y}),
                directory='',
                x_col='image',
                y_col='class',
                class_mode="other",
                target_size=(32, 32),
                batch_size=batch_size)

            model.fit_generator(generator,
                                epochs=epochs,
                                steps_per_epoch=training_steps,
                                validation_data=validation_set,
                                validation_steps=validation_steps,
                                callbacks=callbacks,
                                initial_epoch=init_epoch)
        else:
            model.fit(training_set,
                      epochs=epochs,
                      steps_per_epoch=training_steps,
                      validation_data=validation_set,
                      validation_steps=validation_steps,
                      callbacks=callbacks,
                      initial_epoch=init_epoch)

        self.__logs['training'].info('Training procedure performed successfully!\n')

    def evaluate(self,
                 model: tf.keras.Model,
                 evaluation_set: tf.data.Dataset,
                 evaluation_steps: Union[int, None] = None) -> Union[float, List[float], None]:
        """
        Evaluate the model on provided set.
        :return: the loss value if model has no other metrics, otw returns array with loss and metrics
        values.
        """

        self.__logs['training'].info('Evaluating the model...')

        if evaluation_steps is not None and evaluation_steps == 0:
            self.__logs['training'].warn('Skipping evaluation since provided set is empty')
            return None

        return model.evaluate(evaluation_set, verbose=1, steps=evaluation_steps)

    def predict(self,
                model: tf.keras.Model,
                dataset: tf.data.Dataset,
                verbose: int = 1) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Performs a prediction on a given dataset
        """

        self.__logs['test'].info("Predicting...")

        return model.predict(dataset, verbose=verbose)
