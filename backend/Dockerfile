FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# 安装源。默认走官方源；在国内或代理不可用时，构建时传入镜像地址：
#   DIARY_BUILD_PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
# 镜像地址只影响构建阶段，不写进最终镜像的运行配置。
ARG PIP_INDEX_URL=https://pypi.org/simple
# pip 自身的安装也需要联网，同样受这个参数控制。
ARG PIP_TRUSTED_HOST=

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY serein ./serein

# --index-url 必须在每条 pip 命令上重复：pip 不会把它从一个命令传给另一个。
# 若 PIP_TRUSTED_HOST 为空，这一项会被省略而不是传一个空值（那会让 pip 报错）。
RUN pip_args="--no-cache-dir --index-url ${PIP_INDEX_URL}" \
    && if [ -n "${PIP_TRUSTED_HOST}" ]; then \
         pip_args="${pip_args} --trusted-host ${PIP_TRUSTED_HOST}"; \
       fi \
    && python -m pip install ${pip_args} --upgrade pip \
    && python -m pip install ${pip_args} .

EXPOSE 8000

CMD ["uvicorn", "serein.main:app", "--host", "0.0.0.0", "--port", "8000"]
