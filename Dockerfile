ARG PYTHON_REPO=containers.dev.maio.me/library/python
ARG PYTHON_TAG=latest

FROM ${PYTHON_REPO}:${PYTHON_TAG} AS build

ADD . /source
WORKDIR /source
RUN apk add --no-cache build-base libffi-dev && \
        poetry update && \
        poetry build -f wheel && \
        ( \
            poetry run pip freeze | \
            poetry run xargs pip wheel -w dist \
        )

#
# FINAL APP IMAGE
#

FROM ${PYTHON_REPO}:${PYTHON_TAG}
LABEL maintainer="Sean Johnson <sean@maio.me>"

RUN mkdir /wheels && \
        apk add --no-cache libstdc++
COPY --from=build /source/dist/* /wheels/

RUN pip install /wheels/*

EXPOSE 3000
ENTRYPOINT ["auth0-streams-elasticsearch"]
