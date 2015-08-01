'use strict';

var gulp = require('gulp');
var jsonAngularTranslate = require('./translate');

var paths = gulp.paths;
var i18nHash;

var $ = require('gulp-load-plugins')({
  pattern: ['gulp-*', 'main-bower-files', 'uglify-save-license', 'del']
});

gulp.task('base', ['html'], function() {
  return gulp.src(paths.dist + '/index.html')
    .pipe($.replace('<base href="/">', '<base href="/' + gulp.toolname + '/" />'))
    .pipe(gulp.dest(paths.dist))
    .pipe($.size());
});

gulp.task('i18n-hash', function () {
  return gulp.src('src/i18n/*.json')
    .pipe($.concat('i18n'))
    .pipe($.rev())
    .pipe($.util.buffer(function(err, files) {
      i18nHash = '-' + files[0].revHash;
    }));
});

gulp.task('i18n', ['i18n-hash'], function () {
  if(typeof i18nHash === 'undefined') {
    throw 'i18nHash is undefined';
  }
  return gulp.src('src/i18n/*.json')
    .pipe($.rename(function (path) {
      path.basename += i18nHash;
    }))
    .pipe($.jsonlint())
    .pipe($.jsonlint.reporter())
    .pipe(gulp.dest(paths.dist + '/i18n'))
    .pipe($.size());
});

gulp.task('i18n-autogenerate', function() {
  return gulp.src('src/i18n/*.json')
    .pipe(jsonAngularTranslate("translateAutogenerated.js", {
      module: gulp.toolname
    }))
    .pipe(gulp.dest('src/app'))
});

gulp.task('partials', function () {
  return gulp.src([
    paths.src + '/{app,components}/**/*.html',
    paths.tmp + '/{app,components}/**/*.html'
  ])
    .pipe($.minifyHtml({
      empty: true,
      spare: true,
      quotes: true
    }))
    .pipe($.angularTemplatecache('templateCacheHtml.js', {
      module: 'crosswatch'
    }))
    .pipe(gulp.dest(paths.tmp + '/partials/'));
});

gulp.task('html', ['inject', 'partials', 'i18n-hash'], function () {
  if(typeof i18nHash === 'undefined') {
    throw 'i18nHash is undefined';
  }

  var partialsInjectFile = gulp.src(paths.tmp + '/partials/templateCacheHtml.js', { read: false });
  var partialsInjectOptions = {
    starttag: '<!-- inject:partials -->',
    ignorePath: paths.tmp + '/partials',
    addRootSlash: false
  };

  var htmlFilter = $.filter('*.html');
  var jsFilter = $.filter('**/*.js');
  var appFilter = $.filter('**/app-*.js');
  var cssFilter = $.filter('**/*.css');
  var assets;

  return gulp.src(paths.tmp + '/serve/*.html')
    .pipe($.inject(partialsInjectFile, partialsInjectOptions))
    .pipe(assets = $.useref.assets())
    .pipe($.rev())
    .pipe(appFilter)
    .pipe($.replace('/* gulp:replace */ ""; /* gulp:replace */', '"' + i18nHash + '";'))
    .pipe(appFilter.restore())
    .pipe(jsFilter)
    .pipe($.ngAnnotate())
    .pipe($.uglify({preserveComments: $.uglifySaveLicense}))
    .pipe(jsFilter.restore())
    .pipe(cssFilter)
    .pipe($.csso())
    .pipe(cssFilter.restore())
    .pipe(assets.restore())
    .pipe($.useref())
    .pipe($.revReplace())
    .pipe(htmlFilter)
    .pipe($.minifyHtml({
      empty: true,
      spare: true,
      quotes: true
    }))
    .pipe(htmlFilter.restore())
    .pipe(gulp.dest(paths.dist + '/'))
    .pipe($.size({ title: paths.dist + '/', showFiles: true }));
});

gulp.task('images', function () {
  return gulp.src(paths.src + '/assets/images/**/*')
    .pipe(gulp.dest(paths.dist + '/assets/images/'));
});

gulp.task('fonts', function () {
  return gulp.src($.mainBowerFiles())
    .pipe($.filter('**/*.{eot,svg,ttf,woff,woff2}'))
    .pipe($.flatten())
    .pipe(gulp.dest(paths.dist + '/fonts/'));
});

gulp.task('misc', function () {
  return gulp.src(paths.src + '/{favicon.ico,toolinfo.json}')
    .pipe(gulp.dest(paths.dist + '/'));
});

gulp.task('clean', function (done) {
  $.del([paths.dist + '/', paths.tmp + '/'], done);
});

gulp.task('build', ['html', 'images', 'fonts', 'misc', 'base', 'i18n']);
