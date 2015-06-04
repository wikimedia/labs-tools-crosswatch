'use strict';
angular
  .module('crosswatch')
  .config(function ($provide, $translateProvider) {

    var translationList = [
      {key: 'en', language: 'English', usecases: ['en_US', 'en_GB']},
      {key: 'de', language: 'Deutsch', usecases: ['de_DE', 'de_CH']},
      {key: 'pt', language: 'português', usecases: ['pt_BR']}
    ];

    var availableLangs = [];
    var mappings = {};
    // I know it's ugly, but javascript
    for (var i = 0; i < translationList.length; i++) {
      availableLangs.push(translationList[i].key);
      if (translationList[i].hasOwnProperty('usescases')) {
        for (var j = 0; j < translationList[i].usecases.length; j++) {
          mappings[translationList[i].usecases[j]] = translationList[i].key;
        }
      }
    }

    $provide.constant('translationList', translationList);

    // translation config
    $translateProvider
      .useSanitizeValueStrategy('sanitizeParameters')
      .usePostCompiling(true)
      .useStaticFilesLoader({
        prefix: 'i18n/locale-',
        suffix: '.json'
      })
      .registerAvailableLanguageKeys(availableLangs, mappings)
      .determinePreferredLanguage()
      .fallbackLanguage('en')
      .useStorage('translateStorage');
  })
;
