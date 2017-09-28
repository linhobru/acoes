function checkusername() {
    var usr1 = document.getElementById("username");
    if (usr1.value.length < 5){
        var x = usr1.parentNode.parentNode;
        x.className = "form-group has-error has-feedback";
        var classe = document.getElementById("symbusername");
        classe.className = "glyphicon glyphicon-remove form-control-feedback";
        var message = document.getElementById("msgusername")
        message.style.display = "block";
    }
    else {
        var x = usr1.parentNode.parentNode;
        x.className = "form-group has-success has-feedback";
        var message = document.getElementById("msgusername");
        message.style.display = "none";
        var classe = document.getElementById("symbusername");
        classe.className = "glyphicon glyphicon-ok form-control-feedback";

    }
}

function checkpass() {
    var pass1 = document.getElementById("password");
    var pass2 = document.getElementById("password2");
    if (pass1.value != pass2.value) {
        var x = pass2.parentNode.parentNode;
        x.className = "form-group has-error has-feedback";
        var classe = document.getElementById("symbpass2");
        classe.className = "glyphicon glyphicon-remove form-control-feedback";
        var message = document.getElementById("msgpass2")
        message.style.display = "block";
        return false;
    }
    else {
        var x = pass2.parentNode.parentNode;
        x.className = "form-group has-success has-feedback";
        var message = document.getElementById("msgpass2");
        message.style.display = "none";
        var classe = document.getElementById("symbpass2");
        classe.className = "glyphicon glyphicon-ok form-control-feedback";

    }
}


function mascaraData(campoData){
    var data = campoData.value;
    console.log(data);
    if (data.length == 2){
        data += '/';
        document.getElementById("date").value = data;
        return true;              
    }
    if (data.length == 5){
        data += '/';
        document.getElementById("date").value = data;
        return true;
    }
}

var usr1 = document.getElementById("username");
usr1.onblur = checkusername;

var pass2 = document.getElementById("password2");
pass2.onkeyup = checkpass;

var form = document.getElementsByTagName("form")[0];
form.onsubmit = checkpass;

