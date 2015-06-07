'use strict';

angular.module('crosswatch')
  .controller('MainCtrl', function ($rootScope, authService) {
    var vm = this;
    vm.loggedin = authService.isloggedin();

    $rootScope.$on('login', function (event, msg) {
      vm.loggedin = true;
    });
  });
