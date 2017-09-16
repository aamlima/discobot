'use strict';

angular.module('playerApp', []).factory('playerSSE', function(){
    var eventf = function (func) {
        return function (event) {
            if (event.originalEvent.data) {
                func(JSON.parse(event.originalEvent.data));
            }
        }
    }

    var eventListener = new EventSource('events/');

    eventListener.onmessage = function (event) {
        console.debug(event);
    };

    eventListener.onerror = function (event) {
        console.error(event);
    };

    return {
        on: function(event, callback){
            $(eventListener).on(event, eventf(callback));
        },
        off: function(event){
            $(eventListener).off(event);
        }
    };
}).controller('PlayerController', ['$scope', '$interval', 'playerSSE', function($scope, $interval, playerSSE){
    var seekInterval, seekDelay = 0, ignoredActionCalls = [];

    var setSeekInterval = function(){
        if($scope.player.curItem){
            if(seekInterval && seekDelay != $scope.player.curItem.fps){
                $interval.cancel(seekInterval);
                seekInterval = $interval(function(){if(!$scope.player.paused) $scope.player.frames++;}, 1000/$scope.player.curItem.fps);
                seekDelay = $scope.player.curItem.fps;
            } else if(!seekInterval) {
                seekInterval = $interval(function(){if(!$scope.player.paused) $scope.player.frames++;}, 1000/$scope.player.curItem.fps);
                seekDelay = $scope.player.curItem.fps;
            }
        } else if(seekInterval){
            $interval.cancel(seekInterval);
            seekInterval = undefined;
        }
    };

    playerSSE.on('handshake', function(data){
        $.extend(true, $scope.player, data);
        if($scope.player.curItem) $scope.player.frames = $scope.player.curItem.frame;
        setSeekInterval();
        $scope.$digest();
    });

    playerSSE.on('firstframe', function(data){
        $scope.player.frames = 0;
    });

    playerSSE.on('stats', function(data){
        $.extend(true, $scope.player, data);
        if($scope.player.curItem) $scope.player.frames = $scope.player.curItem.frame;
        setSeekInterval();
        $scope.$digest();
    });

    playerSSE.on('playlistadd', function(data){
        $scope.player.playlist.push(data);
        $scope.player.items--;
        $scope.player.queue++;
        $scope.$digest();
    });

    $scope.ajaxAction = function(action, value, ignoreFirstCall){
        if(ignoreFirstCall && ($.inArray(action, ignoredActionCalls) == -1)){
            ignoredActionCalls.push(action);
            return;
        }
        $.ajax(action+(value != undefined ? '/'+value : ''));
        return false;
    };

    $('#seekControl').on('change', function(){
        $scope.ajaxAction('seek', Math.round($scope.player.frames/$scope.player.curItem.fps));
    });

}]).filter('pct', function(){
    return function(input){
        return Math.round(input*100)+'%';
    }
}).controller('AddController', ['$scope', function($scope){
    $scope.addUrl = function(){
        $.ajax({
            url: 'add',
            type: 'post',
            data: $('form#add').serialize()
        });
        $scope.url = '';
        $scope.playlist = false;
    };
}]);