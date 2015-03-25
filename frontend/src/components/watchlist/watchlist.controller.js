'use strict';

angular.module('watchr')
  .controller('WatchlistCtrl', function ($translate, socket, $http, $log) {
    var vm = this;
    vm.res = [];

    socket.setHandler('message', function (msg) {
      msg = angular.fromJson(msg);
      var data = angular.fromJson(msg.data);
      if (data.msgtype === 'watchlist') {
        vm.res.push(data);
      }
    });

    /*
    $http.get('app/watchlist.json')
      .then(function(res){
        vm.res = angular.fromJson(res.data.watchlist);
        $log.info(vm.res[0]);
      });
      */
  });
