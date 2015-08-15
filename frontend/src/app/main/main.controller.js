'use strict';

angular.module('crosswatch')
  .controller('MainCtrl', function (textDirection, dataService) {
    var vm = this;
    vm.textDirection = textDirection;
    vm.config = dataService.config;
  });
