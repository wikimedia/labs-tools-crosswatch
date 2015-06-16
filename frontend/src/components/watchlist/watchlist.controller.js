'use strict';

angular.module('crosswatch')
  .controller('WatchlistCtrl', function ($translate, socket, $log, dataService, $rootScope, $timeout, $scope) {
    var vm = this;
    vm.watchlist = dataService.watchlist.active;
    vm.config = dataService.config;
    vm.moreWatchlistEntries = dataService.moreWatchlistEntries;

    vm.search = function (text) {
      dataService.filterWatchlist(text);
    };

    vm.icons = {};
    vm.icons['wikibooks']   = "//upload.wikimedia.org/wikipedia/commons/f/fa/Wikibooks-logo.svg";
    vm.icons['wiktionary']  = "//upload.wikimedia.org/wikipedia/commons/e/ef/Wikitionary.svg";
    vm.icons['wikiquote']   = "//upload.wikimedia.org/wikipedia/commons/f/fa/Wikiquote-logo.svg";
    vm.icons['wikipedia']   = "//upload.wikimedia.org/wikipedia/commons/8/80/Wikipedia-logo-v2.svg";
    vm.icons['wikinews']    = "//upload.wikimedia.org/wikipedia/commons/2/24/Wikinews-logo.svg";
    vm.icons['wikivoyage']  = "//upload.wikimedia.org/wikipedia/commons/8/8a/Wikivoyage-logo.svg";
    vm.icons['wikisource']  = "//upload.wikimedia.org/wikipedia/commons/4/4c/Wikisource-logo.svg";
    vm.icons['wikiversity'] = "//upload.wikimedia.org/wikipedia/commons/9/91/Wikiversity-logo.svg";
    vm.icons['foundation']  = "//upload.wikimedia.org/wikipedia/commons/c/c4/Wikimedia_Foundation_RGB_logo_with_text.svg";
    vm.icons['mediawiki']   = "//upload.wikimedia.org/wikipedia/commons/3/3d/Mediawiki-logo.png";
    vm.icons['meta']        = "//upload.wikimedia.org/wikipedia/commons/7/75/Wikimedia_Community_Logo.svg";
    vm.icons['wikidata']    = "//upload.wikimedia.org/wikipedia/commons/f/ff/Wikidata-logo.svg";
    vm.icons['commons']     = "//upload.wikimedia.org/wikipedia/commons/4/4a/Commons-logo.svg";
    vm.icons['species']     = "//upload.wikimedia.org/wikipedia/en/b/bf/Wikispecies-logo-35px.png";
    vm.icons['incubator']   = "//upload.wikimedia.org/wikipedia/commons/e/e3/Incubator-logo.svg";
    vm.icons['test']        = "//upload.wikimedia.org/wikipedia/commons/4/4a/Wikipedia_logo_v2_%28black%29.svg";

    vm.flags = ["ad", "ae", "af", "ag", "ai", "al", "am", "an", "ao", "ar", "as", "at", "au", "aw", "ax", "az", "ba", "bb", "bd", "be", "bf", "bg", "bh", "bi", "bj", "bm", "bn", "bo", "br", "bs", "bt", "bv", "bw", "by", "bz", "ca", "cc", "cd", "cf", "cg", "ch", "ci", "ck", "cl", "cm", "cn", "co", "cr", "cs", "cu", "cv", "cx", "cy", "cz", "da", "de", "dj", "dk", "dm", "do", "dz", "ec", "ee", "eg", "eh", "en", "er", "es", "et", "fam", "fi", "fj", "fk", "fm", "fo", "fr", "ga", "gb", "gd", "ge", "gf", "gh", "gi", "gl", "gm", "gn", "gp", "gq", "gr", "gs", "gt", "gu", "gw", "gy", "he", "hk", "hm", "hn", "hr", "ht", "hu", "id", "ie", "il", "in", "io", "iq", "ir", "is", "it", "jm", "jo", "jp", "ke", "kg", "kh", "ki", "km", "kn", "kp", "kr", "kw", "ky", "kz", "la", "lb", "lc", "li", "lk", "lr", "ls", "lt", "lu", "lv", "ly", "ma", "mc", "md", "me", "mg", "mh", "mk", "ml", "mm", "mn", "mo", "mp", "mq", "mr", "ms", "mt", "mu", "mv", "mw", "mx", "my", "mz", "na", "nc", "ne", "nf", "ng", "ni", "nl", "no", "np", "nr", "nu", "nz", "om", "pa", "pe", "pf", "pg", "ph", "pk", "pl", "pm", "pn", "pr", "ps", "pt", "pw", "py", "qa", "re", "ro", "rs", "ru", "rw", "sa", "sb", "scotland", "sc", "sd", "se", "sg", "sh", "si", "sj", "sk", "sl", "sm", "sn", "so", "sr", "st", "sv", "sy", "sz", "tc", "td", "tf", "tg", "th", "tj", "tk", "tl", "tm", "tn", "to", "tr", "tt", "tv", "tw", "tz", "ua", "ug", "um", "us", "uy", "uz", "va", "vc", "ve", "vg", "vi", "vn", "vu", "wales", "wf", "ws", "ye", "yt", "za", "zh", "zm", "zw"];

    vm.flagurl = function (lang) {
      if (vm.flags.indexOf(lang) >= 0) {
        return "assets/images/flags/png/" + lang + ".png";
      } else {
        return false;
      }
    };
  });
