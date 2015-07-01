'use strict';

angular.module('crosswatch')
  .controller('NotificationsCtrl', function ($translate, $log, dataService) {
    var vm = this;
    vm.icons = dataService.icons;
    vm.flagurl = dataService.flagurl;
    vm.notifications = dataService.notifications;
    vm.config = dataService.config;
    vm.markNotificationsRead = dataService.markNotificationsRead;
  });
