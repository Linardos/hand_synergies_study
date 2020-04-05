import tensorflow as tf
from tensorboard.plugins.hparams import api as hp
import os
import tensorflow.keras.backend as K


class Regression_Model():

    def r_square(self, y_true, y_pred):
        SS_res = K.sum(K.square(y_true - y_pred))
        SS_tot = K.sum(K.square(y_true - K.mean(y_true)))
        return (1 - SS_res / (SS_tot + K.epsilon()))

    # Define metrics to watch
    METRICS = [
        tf.keras.metrics.MeanSquaredError(name='mse'),
        tf.keras.metrics.MeanAbsoluteError(name='mae'),
        tf.keras.metrics.RootMeanSquaredError(name='rmse')
    ]

    # Set hyper parameter search
    # HP_HIDDEN_UNITS = hp.HParam('hidden_units', hp.Discrete([10, 50, 200]))
    HP_HIDDEN_UNITS = hp.HParam('hidden_units', hp.Discrete([10, 50, 100, 300]))
    # HP_DROPOUT = hp.HParam('dropout', hp.Discrete([0.0, 0.1, 0.2]))
    HP_DROPOUT = hp.HParam('dropout', hp.Discrete([0.0, 0.2, 0.4]))
    HP_HIDDEN_LAYERS = hp.HParam('hidden_layers', hp.Discrete([1, 2]))
    HP_WINDOW_SIZE = hp.HParam('window_size', hp.Discrete([3, 5, 10, 15, 20]))
    HP_RNN = hp.HParam('rnn', hp.Discrete(['vanilla', 'gru', 'lstm']))
    # use adam directly
    HP_LEARNING_RATE = hp.HParam('learning_rate', hp.Discrete([0.001, 0.01, 0.0001]))
    HP_BATCH_SIZE = hp.HParam('batch_size', hp.Discrete([32, 64]))

    def __init__(self, window_size, n_features):
        self.window_size = window_size
        self.n_features = n_features
        self.configurations = self.__build_configurations()

    def __build_configurations(self):
        configurations = []
        for hl in self.HP_HIDDEN_LAYERS.domain.values:
            for dr in self.HP_DROPOUT.domain.values:
                for rnn in self.HP_RNN.domain.values:
                    for hu in self.HP_HIDDEN_UNITS.domain.values:
                        for lr in self.HP_LEARNING_RATE.domain.values:
                            for bs in self.HP_BATCH_SIZE.domain.values:
                                new = self.__build_conf(hl, dr, rnn, hu, lr, bs)
                                configurations.append(new)
        return configurations

    def __get_rnn_model(self, rnn_model, hidden_layers, dropout, hidden_units):
        lstm_layers = []

        if hidden_layers == 1:
            if rnn_model == 'lstm':
                lstm_layers.append(tf.keras.layers.LSTM(hidden_units,
                                                        activation='relu',
                                                        input_shape=(self.window_size, self.n_features),
                                                        name="lstm_0_%dU" % hidden_units))
            elif rnn_model == 'gru':
                lstm_layers.append(tf.keras.layers.GRU(hidden_units,
                                                       activation='relu',
                                                       input_shape=(self.window_size, self.n_features),
                                                       name="gru_0_%dU" % hidden_units))
            else:
                lstm_layers.append(tf.keras.layers.SimpleRNN(hidden_units,
                                                             activation='relu',
                                                             input_shape = (self.window_size, self.n_features),
                                                             name = "vanilla_0_%dU" % hidden_units))
        else:
            if rnn_model == 'lstm':
                lstm_layers.append(
                    tf.keras.layers.LSTM(hidden_units,
                                         activation='relu',
                                         input_shape=(self.window_size, self.n_features),
                                         return_sequences=True,
                                         name="lstm_0_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_0"))
                lstm_layers.append(
                    tf.keras.layers.LSTM(hidden_units, activation='relu', name="lstm_1_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_1"))
            elif rnn_model == 'gru':
                lstm_layers.append(
                    tf.keras.layers.GRU(hidden_units,
                                        input_shape=(self.window_size, self.n_features),
                                        activation='relu',
                                        return_sequences=True,
                                        name="gru_0_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_0"))
                lstm_layers.append(
                    tf.keras.layers.GRU(hidden_units, activation='relu', name="gru_1_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_1"))
            else:
                lstm_layers.append(
                    tf.keras.layers.SimpleRNN(hidden_units,
                                              input_shape=(self.window_size, self.n_features),
                                              activation='relu',
                                              return_sequences=True,
                                        name="vanilla_0_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_0"))
                lstm_layers.append(
                    tf.keras.layers.SimpleRNN(hidden_units, activation='relu', name="vanilla_1_%dU" % hidden_units))
                # lstm_layers.append(tf.keras.layers.ReLU(name="input_RELU_1"))

        output_layers = [tf.keras.layers.Dropout(dropout, name="D%.2f" % dropout),
                         tf.keras.layers.Dense(1, name="angle_delta_output")]
                                               # activation=lambda x: 180*tf.keras.activations.tanh(x))]

        model = tf.keras.models.Sequential(name="awsome_net", layers=lstm_layers + output_layers)

        return model

    def __get_callbacks(self, logdir, hparams):
        callbacks = [tf.keras.callbacks.TerminateOnNaN(),
                     tf.keras.callbacks.TensorBoard(logdir,
                                                    update_freq='batch',
                                                    write_graph=False,
                                                    histogram_freq=5),
                     tf.keras.callbacks.EarlyStopping(monitor='val_mse',
                                                      patience=15),
                     hp.KerasCallback(logdir, hparams, trial_id=logdir),
                     tf.keras.callbacks.ModelCheckpoint(
                         filepath=os.path.join(logdir, "cp.ckpt"),
                         save_best_only=True,
                         monitor='val_mse',
                         verbose=1)
                     ]
        return callbacks


    def __build_conf(self, hl, dr, rnn, hu, lr, bs):
        model = self.__get_rnn_model(rnn_model=rnn, hidden_layers= hl, dropout=dr, hidden_units=hu)
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
                      loss=tf.keras.losses.MeanSquaredError(),
                      metrics=[self.METRICS]
                      )

        # Run log dir
        hparams_log_dir = os.path.join("/content/drive/", "My Drive", "rnn-hyper-param-search", "logs")
        # hparams_log_dir = os.path.join("results", "rnn-hyper-param-search", "logs")
        logdir = os.path.join(hparams_log_dir, "rnn=%s-hl=%d-dr=%d-hu=%d-lr=%s-bs=%d-ws-%d" %
                              (rnn, hl, dr, hu, lr, bs, self.window_size))

        if os.path.exists(logdir):
            pass
            # print("Ignoring run %s" % logdir)
        hparams = {
            self.HP_HIDDEN_LAYERS: hl,
            self.HP_DROPOUT: dr,
            self.HP_RNN: rnn,
            self.HP_HIDDEN_UNITS: hu,
            self.HP_LEARNING_RATE: lr,
            self.HP_BATCH_SIZE: bs,
            self.HP_WINDOW_SIZE: self.window_size
        }
        callbacks = self.__get_callbacks(logdir, hparams)

        return model, callbacks, bs
