'use strict';

angular.module('watchr')
  .controller('WatchlistCtrl', function ($translate, socket, $log, dataService) {
    var vm = this;
    vm.watchlist = dataService.watchlist;
    vm.echolist = dataService.echolist;
    vm.icons = dataService.icons;
    vm.testicon = {};
    vm.flags = dataService.flags;

    vm.flagurl = function (lang) {
      if (vm.flags.indexOf(lang) >= 0) {
        return "assets/images/flags/png/" + lang + ".png";
      } else {
        return false;
      }
    };
  });
