#!/usr/bin/env node
// 翼德 · 重建 lessons 编译索引(.meta/lessons-index.json)。record / consolidate 写完 lessons 后调用。
'use strict';
const path = require('path');
const { buildIndex } = require(path.join(__dirname, 'lessons.js'));
const list = buildIndex();
console.log(`OK\t已重建索引,共 ${list.length} 条 lessons。`);
