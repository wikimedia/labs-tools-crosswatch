'use strict';

angular.module('crosswatch')
  .controller('MainCtrl', function (textDirection) {
    var vm = this;
    vm.textDirection = textDirection;
  });
