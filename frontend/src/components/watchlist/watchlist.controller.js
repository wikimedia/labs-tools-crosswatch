'use strict';

angular.module('crosswatch')
  .controller('WatchlistCtrl', function ($translate, socket, $log, dataService, $rootScope) {
    var vm = this;
    vm.watchlist = dataService.watchlist;
    vm.echolist = dataService.echolist;
    vm.icons = dataService.icons;
    vm.flags = dataService.flags;
    vm.config = dataService.config;
    vm.saveConfig = dataService.saveConfig;

    updatePeriodList();
    $rootScope.$on('$translateChangeSuccess', updatePeriodList);

    function updatePeriodList () {
      var hours = [0.5, 1, 1.5];
      var days = [2, 3, 7, 14, 21, 30];

      vm.periodList = [];
      var addItem = function (value) {
        return function (label) {
          vm.periodList.push({value: value, label: label})
        }
      };
      for (var i=0; i<hours.length; i++) {
        $translate('HOURS', {number: 24*hours[i]}).then(addItem(hours[i]));
      }
      for (var j=0; j<days.length; j++) {
        $translate('DAYS', {number: days[j]}).then(addItem(days[j]));
      }
    }

    vm.resetWatchlist = function () {
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
