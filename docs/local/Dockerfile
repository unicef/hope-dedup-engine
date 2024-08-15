FROM ruby:3.3.4

RUN gem install bundler:2.5.9

WORKDIR /usr/src/app
COPY . .

RUN bundle install \
    && bundle exec jekyll build --baseurl '/hde-doc'

CMD ["jekyll",  "serve",  "--host",  "0.0.0.0"]
