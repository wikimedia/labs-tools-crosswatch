'use strict';

var gulp = require('gulp');

gulp.toolname = 'crosswatch'

gulp.paths = {
  src: 'src',
  dist: 'dist/' + gulp.toolname,
  tmp: '.tmp',
  e2e: 'e2e'
};

require('require-dir')('./gulp');

gulp.task('default', ['clean'], function () {
    gulp.start('build');
});
