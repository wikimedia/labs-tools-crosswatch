'use strict';

angular.module('crosswatch')
  .controller('WatchlistCtrl', function ($translate, socket, $log, dataService) {
    var vm = this;
    vm.watchlist = dataService.watchlist;
    vm.echolist = dataService.echolist;
    vm.icons = dataService.icons;
    vm.flags = dataService.flags;
    vm.config = dataService.config;
    vm.saveConfig = dataService.saveConfig;

    vm.lastrevonlyChanged = function () {
      dataService.resetWatchlist();
      vm.watchlist = dataService.watchlist;
    };

    vm.flagurl = function (lang) {
      if (vm.flags.indexOf(lang) >= 0) {
        return "assets/images/flags/png/" + lang + ".png";
      } else {
        return false;
      }
    };
  });
