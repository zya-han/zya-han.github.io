—
layout: page
title: All Comments
permalink: /admin-comments
lang: ko
locale: ko
hidden: true
—

<div class=“remark42__last-comments” data-max=“100”></div>

<script>
  var remark_config = {
    host: “https://comments.zyahan.blog”,
    site_id: “zyahan”,
    components: [“last-comments”]
  };
</script>
<script>
  !function(e,n){for(var o=0;o<e.length;o++){var r=n.createElement(“script”),c=“.js”,d=n.head||n.body;”noModule”in r?(r.type=“module”,c=“.mjs”):r.async=!0,r.defer=!0,r.src=remark_config.host+”/web/“+e[o]+c,d.appendChild(r)}}(remark_config.components||[“last-comments”],document);
</script>
