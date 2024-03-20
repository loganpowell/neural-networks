```
Watch a great overview: https://www.youtube.com/watch?v=TkwXa7Cvfr8
```

# Neural networks are "universal" function approximators

Neural networks are function approximators. They are used to approximate
functions that are too complex to be represented by a simple mathematical
formula. This is done by training the network on a dataset of input-output
pairs. The network learns to map inputs to outputs by adjusting its internal
parameters, which are called weights and biases. Once trained, the network can
be used to make predictions on new inputs.

\(f(x) \sim NN(x)\)

Where \(f(x)\) is the true function, and \(NN(x)\) is the neural network's
approximation of the function.

|                         |                                                                                                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![](./assets/nn/1.png)  | In conventional programming, we create functions that take input data and produce output data                                                                     |
| ![](./assets/nn/2.png)  | For example, we can use a \(sin\) function to have a deterministic effect \(y\) for any given input \(x\)                                                         |
| ![](./assets/nn/3.png)  | In two-dimensional space, we can plot the \(sin\) function as a curve that maps every \(x\) to a \(y\)                                                            |
| ![](./assets/nn/4.png)  | If we don't have a function - but do have inputs and outputs - we can use a NN to approximate the function                                                        |
| ![](./assets/nn/5.png)  | Training a NN involves tweaking the network parameters to minimize error between predicted and true outputs                                                       |
| ![](./assets/nn/6.png)  | We can leverage the same NN to approximate different functions by training it on different datasets                                                               |
| ![](./assets/nn/7.png)  | Thus a NN is a "universal" function approximator, capable of learning and approximating any function                                                              |
| ![](./assets/nn/8.png)  | A NN is a graph composed of layers of **neurons**, which are interconnected by **edges**. These layers connect inputs to predicted outputs.                       |
| ![](./assets/nn/9.png)  | A **neuron** is a tiny mathematical function that has many inputs and a single output.                                                                            |
| ![](./assets/nn/10.png) | We calculate the output of a neuron by summing the products of its inputs and their corresponding weights.                                                        |
| ![](./assets/nn/11.png) | We add an additional weight to the sum, called the **bias** to enable the network to shift the function.                                                          |
| ![](./assets/nn/12.png) | We use matrix multiplication to calculate the effect of the weights and biases on the inputs, where the weights are the parameters of the network.                |
| ![](./assets/nn/13.png) | Here's an example of the dot product of a matrix and a vector.                                                                                                    |
| ![](./assets/nn/14.png) | We then sum the result of that dot product.                                                                                                                       |
| ![](./assets/nn/15.png) | We then apply an **activation function** to the result of the sum to introduce non-linearity into the network.                                                    |
| ![](./assets/nn/16.png) | This non-linearity allows the network to approximate complex, multi-variable functions.                                                                           |
| ![](./assets/nn/17.png) | The **ReLU** function is a common activation function                                                                                                             |
| ![](./assets/nn/18.png) | For any value of \(x\), the ReLU function returns \(x\) if \(x\) is positive, and \(0\) otherwise                                                                 |
| ![](./assets/nn/19.png) | The output of the activation function is then passed to the neurons in the next layer                                                                             |
| ![](./assets/nn/20.png) | These calculations are repeated for each layer of the network, until the final output is produced                                                                 |
| ![](./assets/nn/22.png) | As more layers are added to the network, it becomes capable of approximating more complex functions                                                               |
| ![](./assets/nn/23.png) | More complex functions are better equipped to approximate real-world phenomena                                                                                    |
| ![](./assets/nn/24.png) | We measure the difference between the predicted outputs and the true outputs using a **loss function**. Here a simple function is approximated: \(y = f(x)\)      |
| ![](./assets/nn/43.png) | Over-fitting can occur when the network learns to memorize the training data, rather than learning to find the underlying patterns in the data.                   |
| ![](./assets/nn/25.png) | This can be visualized for lower-dimensional data as the distance between the predicted and true outputs                                                          |
| ![](./assets/nn/26.png) | Let's say we need to predict the value of a pixel given a row and column index of the pixel. Here \(R^2 \rightarrow R^1\), where \(R\) is the set of real numbers |
| ![](./assets/nn/27.png) | And our data set is all the pixels in this image, and \(R^2\) is the set of all possible row/column inputs and \(R^1\) is the set of all possible pixel values    |
| ![](./assets/nn/28.png) | As we train, we can view the function approx. as a 2d plane, and for each pixel, we can view the predicted value                                                  |
| ![](./assets/nn/29.png) | Our row/column inputs range from 0 to 1439, and the pixel values range from 0 to 255                                                                              |
| ![](./assets/nn/30.png) | So, we scale the values to -1 to 1, because it's smaller and centered around 0, which is better for approximation                                                 |
| ![](./assets/nn/31.png) | We are also going to use a "Leaky ReLU" activation function, can output negative values, but are small                                                            |
| ![](./assets/nn/32.png) | because the final output is a pixel value, we need the output to be between 0 and 1                                                                               |
| ![](./assets/nn/33.png) | We can use sigmoid activation function to scale the output to the desired range                                                                                   |
| ![](./assets/nn/34.png) | However, using a normalized tanh activation function is better for the network                                                                                    |
| ![](./assets/nn/35.png) | We can verify this by looking at the loss function, which is the difference between the predicted and true outputs                                                |
| ![](./assets/nn/36.png) | Let's attempt to approximate a parametric surface, that takes a 2d input and produces a 3d output                                                                 |
| ![](./assets/nn/37.png) | Let's use a dataset created by sampling the surface of a sphere, and use a NN to approximate the surface                                                          |
| ![](./assets/nn/38.png) | We can visualize the approximation as a 3d surface, and for each input, we can view the predicted output                                                          |
| ![](./assets/nn/39.png) | A similar approach can be used to approximate a function that takes a hand-drawn number and produces a predicted digit (label)                                    |
| ![](./assets/nn/40.png) | The image is made of 28x28 pixels, and the label is a number from 0 to 9                                                                                          |
| ![](./assets/nn/42.png) | The NN's job is to produce a probability distribution over the 10 possible labels for any given input image                                                       |

```mermaid
sequenceDiagram
    participant x as Input
    participant W1 as Weights 1
    participant b1 as Biases 1
    participant h1 as Hidden Layer
    participant W2 as Weights 2
    participant b2 as Biases 2
    participant y as Output
    participant t as True Output
    loop Training
        alt forward pass
            x ->> W1: Multiply
            W1 ->> b1: Add
            b1 ->> h1: Activation
            h1 ->> W2: Multiply
            W2 ->> b2: Add
            b2 ->> y: Activation
        end
        alt loss function
            y ->> t: Loss Function
            t ->> y: Loss Function
        end
        alt backward pass
            y ->> W2: Gradients
            y ->> b2: Gradients
            W2 ->> h1: Gradients
            b2 ->> h1: Gradients
            h1 ->> W1: Gradients
            h1 ->> b1: Gradients
            W1 ->> x: Gradients
            b1 ->> x: Gradients
        end
    end
```

# The Forward Pass

The forward pass is the process of feeding the inputs forward through the
network and computing the predicted outputs. This is done by applying the
weights and biases to the inputs and passing the result through the activation
functions of the neurons.

The forward pass can be represented as a series of matrix multiplications and
additions. The inputs are multiplied by the weights of the input layer to the
hidden layer, and the result is added to the biases of the hidden layer. The
result is then passed through the activation function of the hidden layer to
produce the inputs to the output layer. The inputs to the output layer are
multiplied by the weights of the hidden layer to the output layer, and the
result is added to the biases of the output layer. The result is then passed
through the activation function of the output layer to produce the predicted
outputs.

The forward pass can be represented as follows:

```
h1 = activation(W1 * x + b1)
y = activation(W2 * h1 + b2)
```

Where x is the input vector, W1 and W2 are the weights matrices, b1 and b2 are
the biases vectors, h1 is the hidden layer output, and y is the predicted
output.

# Activation Functions

The activation functions of the neurons are used to introduce non-linearity
into the network. This allows the network to approximate complex functions
that are not linear. There are many different activation functions that can be
used, such as the sigmoid function, the hyperbolic tangent function, and the
rectified linear unit (ReLU) function.

The sigmoid function is defined as:

```
sigmoid(x) = 1 / (1 + exp(-x))
```

The hyperbolic tangent function is defined as:

```
tanh(x) = (exp(x) - exp(-x)) / (exp(x) + exp(-x))
```

The ReLU function is defined as:

```
ReLU(x) = max(0, x)
```

Each of these activation functions has its own properties and is suitable for
different types of problems. The choice of activation function depends on the
specific problem being solved and the characteristics of the data.

# The Loss Function

The loss function is used to measure the difference between the predicted
outputs and the true outputs. The loss function is a measure of how well the
network is performing, and it is used to guide the process of updating the
weights and biases of the network.

There are many different loss functions that can be used, such as the mean
squared error (MSE) function, the cross-entropy function, and the hinge loss
function.

The mean squared error function is defined as:

```
MSE(y, t) = (1 / n) * sum((y - t)^2)
```

The cross-entropy function is defined as:

```
cross_entropy(y, t) = -sum(t * log(y) + (1 - t) * log(1 - y))
```

The hinge loss function is defined as:

```
hinge_loss(y, t) = max(0, 1 - y * t)
```

Each of these loss functions has its own properties and is suitable for
different types of problems. The choice of loss function depends on the
specific problem being solved and the characteristics of the data.

Let's draw a table to represent the loss function.

| Function           | Definition                              |
| ------------------ | --------------------------------------- |
| Mean Squared Error | (1 / n) \* sum((y - t)^2)               |
| Cross-Entropy      | -sum(t _ log(y) + (1 - t) _ log(1 - y)) |
| Hinge Loss         | max(0, 1 - y \* t)                      |

# The Backward Pass

The backward pass is the process of updating the weights and biases of the
network in order to minimize the difference between the predicted outputs and
the true outputs. This is done by computing the gradients of the loss function
with respect to the weights and biases, and then using these gradients to
update the parameters of the network.

The gradients are computed using the chain rule of calculus, which allows the
gradients of the loss function to be expressed in terms of the gradients of the
activation functions. The gradients are then used to update the weights and
biases of the network using an optimization algorithm, such as gradient
descent.

The process of updating the weights and biases of the network is repeated many
times until the network's predictions are accurate enough. This process is
called training, and it is the most important part of building a neural
network.

# Putting It All Together

In summary, a neural network is a function approximator that is trained on a
dataset of input-output pairs. The network is composed of layers of neurons,
which are interconnected by edges. The weights and biases of the network are
learned through a process called backpropagation, which adjusts the parameters
of the network in order to minimize the difference between the predicted
outputs and the true outputs.
