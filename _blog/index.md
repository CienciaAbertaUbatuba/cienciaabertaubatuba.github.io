---
layout: default
title: Blog
permalink: /blog/
---

<div class="post-list">
  {% assign posts_to_list = site.blog | default: site.posts | sort: 'date' | reverse %}
  {% for post_item in posts_to_list %}
    <article class="mb-4 pb-3 border-bottom">
      <h3><a href="{{ post_item.url | relative_url }}">{{ post_item.title }}</a></h3>
      <p class="text-muted small">
        {% if post_item.date %}Publicado em: {{ post_item.date | date: "%d/%m/%Y" }}{% endif %}
        {% if post_item.author %} por {{ post_item.author }}{% endif %}
      </p>
      {{ post_item.content | strip_html | truncatewords: 30 }}
      <p><a href="{{ post_item.url | relative_url }}">Leia mais...</a></p>
    </article>
  {% endfor %}
</div>