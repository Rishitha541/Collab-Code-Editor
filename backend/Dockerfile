FROM python:3.11-slim

# Create a non-root user so code running inside the container
# can't do anything with elevated privileges on the host system.
RUN useradd -m sandboxuser
USER sandboxuser

WORKDIR /sandbox

# No extra packages installed on purpose — keeps the image small
# and reduces what user-submitted code could potentially exploit.