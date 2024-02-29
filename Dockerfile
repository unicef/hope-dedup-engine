FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04 as base

RUN apt-get update \
    && apt-get install -y \
        python3 \
        python3-pip \
        gcc-9 g++-9 \
        git \
        build-essential \
        cmake curl \
        libgtk2.0-dev \
        pkg-config \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        python3-dev \
        python3-numpy \
        nvidia-cuda-toolkit \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 82 hde \
    && adduser \
        --system --uid 82 \
        --disabled-password --home /home/hde \
        --shell /sbin.nologin --group hde --gecos hde \
    && mkdir -p /code /tmp /data /static \
    && chown -R hde:hde /code /tmp /data /static

# Install cuDNN
COPY cudnn-local-repo-ubuntu2204-8.9.7.29_1.0-1_amd64.deb /tmp
RUN dpkg -i /tmp/cudnn-local-repo-ubuntu2204-8.9.7.29_1.0-1_amd64.deb 
RUN cp /var/cudnn-local-repo-ubuntu2204-8.9.7.29/cudnn-local-8AE81B24-keyring.gpg /usr/share/keyrings/ 
RUN apt-get update \
    && apt-get install -y libcudnn8=8.9.7.29-1+cuda11.8 libcudnn8-dev=8.9.7.29-1+cuda11.8 \
    && rm -rf /var/lib/apt/lists/* \
    && rm /tmp/cudnn-local-repo-ubuntu2204-8.9.7.29_1.0-1_amd64.deb

# Clone and build OpenCV from source
RUN git clone https://github.com/opencv/opencv.git \
    && git clone https://github.com/opencv/opencv_contrib.git \
    && cd opencv \
    && mkdir build \
    && cd build \
    && cmake -D CMAKE_BUILD_TYPE=RELEASE \
             -D CMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/ \
             -D CUDA_HOST_COMPILER=/usr/bin/gcc-9 \
             -D CMAKE_INSTALL_PREFIX=/usr/local \
             -D INSTALL_C_EXAMPLES=OFF \
             -D INSTALL_PYTHON_EXAMPLES=OFF \
             -D WITH_CUDA=ON \
             -D CUDA_ARCH_BIN=5.2 \
             -D CUDA_ARCH_PTX="" \
             -D BUILD_opencv_cudacodec=OFF \
             -D ENABLE_FAST_MATH=1 \
             -D CUDA_FAST_MATH=1 \
             -D WITH_CUBLAS=1 \
             -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
             -D BUILD_EXAMPLES=OFF .. \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && cd ../../ \
    && rm -rf opencv opencv_contrib

# Clone and build dlib from source with CUDA support
RUN git clone https://github.com/davisking/dlib.git \
    && cd dlib \
    && mkdir build \
    && cd build \
    && cmake .. -DDLIB_USE_CUDA=1 -DUSE_AVX_INSTRUCTIONS=1 -DCUDA_HOST_COMPILER=/usr/bin/gcc-9 -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/ \
    && cmake --build . \
    && cd .. \
    && python3 setup.py install \
    && cd .. \
    && rm -rf dlib

RUN pip install face-recognition

ENV PACKAGES_DIR=/packages
ENV PYPACKAGES=$PACKAGES_DIR/__pypackages__/3.11
ENV LIB_DIR=$PYPACKAGES/lib
ENV PYTHONPATH=$PYTHONPATH:$LIB_DIR:/code/src
ENV PATH=$PATH:$PYPACKAGES/bin

WORKDIR /code

FROM base as builder

WORKDIR $PACKAGES_DIR
RUN pip install pdm==2.9.3
ADD pyproject.toml ./
ADD pdm.toml.template ./pdm.toml
ADD pdm.lock ./
RUN pdm sync --prod --no-editable --no-self

FROM builder AS dev

RUN pdm sync --no-editable --no-self

WORKDIR /code
COPY ./ ./

ADD docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]


FROM base AS prd

ENV PATH=$PATH:/code/.venv/bin/

COPY --chown=hde:hde ./ ./
COPY --chown=hde:hde --from=builder $PACKAGES_DIR $PACKAGES_DIR
USER hde

ADD docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]