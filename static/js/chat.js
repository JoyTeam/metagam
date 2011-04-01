Chat = {
	msg: function(pkt) {
		alert(pkt.html);
	}
};
Game.stream_handler('chat', Chat);
loaded('chat');
