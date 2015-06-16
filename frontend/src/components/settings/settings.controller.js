'use strict';

angular.module('crosswatch')
  .controller('SettingsCtrl', function ($translate, $route, $log, dataService, $rootScope) {
    var vm = this;
    vm.config = dataService.config;
    vm.oldconfig = vm.config;
    vm.saveConfig = function () {
      dataService.saveConfig();
      dataService.filterWatchlist('watchlist', dataService.config);
    };

    vm.reload = function () {
      $route.reload();
    };

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
        $translate('SHOW_LAST_HOURS', {number: 24*hours[i]}).then(addItem(hours[i]));
      }
      for (var j=0; j<days.length; j++) {
        $translate('SHOW_LAST_DAYS', {number: days[j]}).then(addItem(days[j]));
      }
    }

    vm.resetWatchlist = function () {
      $log.info('resetting watchlist');
      dataService.resetWatchlist();
    };
  });
